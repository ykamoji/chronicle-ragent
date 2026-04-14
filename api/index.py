from api.db.cache import cache_session_docs_background
import logging
import threading
import time
import json
from api.agent.tools import TOOLS_NAME_MAP
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from api.agent.orchestrator import run_agent_stream, interrupt_agent
from api.agent.memory import memory
from api.ingestion.worker import start_ingession
from api.db.mongo import mongo
from api.db.cache import session_cache
from api.config.settings import app_settings

# Basic Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Hide verbose HTTP and GenAI info logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("google_genai.models").setLevel(logging.WARNING)

app = Flask(__name__)
# Allow CORS from everywhere for Next.js proxy/LAN interaction
CORS(app)


@app.route("/health", methods=["GET"])
def health_check():

    try:
        details = {}
        mongo.client.admin.command("ping")
        if mongo.client:
            sess = mongo.get_sessions_collection()
            details["DB"] = mongo.db.name
            details[sess.name] = {
                "count": sess.count_documents({})
            }
            vec = mongo.get_vector_collection()
            details[vec.name] = {
                "count": vec.count_documents({})
            }
            msg = mongo.get_messages_collection()
            details[msg.name] = {
                "count": msg.count_documents({})
            }
            ana = mongo.get_analytics_collection()
            details[ana.name] = {
                "count": ana.count_documents({})
            
            }        
            return jsonify({"status": "healthy", "details":details, "mongo_connected": True})

    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        return jsonify({"status": "unhealthy", "details":details, "mongo_connected": False})


@app.route("/settings", methods=["GET", "PUT"])
def handle_settings():
    """GET returns current settings; PUT updates active model / delay override."""
    if request.method == "GET":
        return jsonify(app_settings.to_dict())

    # PUT
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400

    if "model" in data:
        ok = app_settings.set_model(data["model"])
        if not ok:
            return jsonify({"error": f"Unknown model: {data['model']}"}), 400

    if "delayOverride" in data:
        val = data["delayOverride"]
        app_settings.set_delay_override(val if val is not None and val != "" else None)

    return jsonify(app_settings.to_dict())


@app.route("/query", methods=["POST"])
def query_agent():
    """Hits the main ReAct agent with a user query, streaming steps via SSE."""
    if not mongo.client:
        return jsonify({"error": "MongoDB is not connected. Agent cannot retrieve data."}), 503

    data = request.get_json()
    if not data or "query" not in data:
        return jsonify({"error": "Missing 'query' field in JSON."}), 400

    user_query = data.get("query")
    session_id = data.get("session_id")

    if not session_id:
        session_id = memory.create_conversation()

    logger.info(f"Starting agent stream for session: {session_id}")

    def generate():
        for event_json in run_agent_stream(session_id, user_query):
            yield f"data: {event_json}\n\n"
            
            # Check for error type for automatic cleanup
            try:
                event = json.loads(event_json)
                if event.get("type") == "error":
                    logger.warning(f"Error detected in stream for session {session_id}. Running cleanup.")
                    memory.delete_last_query_internals(session_id)
                    return
            except Exception as e:
                logger.debug(f"Event not checkable for cleanup: {e}")

    return Response(generate(), content_type='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
        'Connection': 'keep-alive'
    })


@app.route("/query/cleanup", methods=["POST"])
def cleanup_failed_query():
    """Cleans up MongoDB after a query fails to complete.

    Removes the failed user query and all hidden internal messages (agent
    thoughts, system observations) that were written during the failed round,
    so the session history stays clean and the query can safely be retried.
    """
    data = request.get_json()
    if not data or "session_id" not in data:
        return jsonify({"error": "Missing 'session_id' field"}), 400

    session_id = data["session_id"]
    removed = memory.delete_last_query_internals(session_id)
    logger.info(f"Cleaned up {removed} messages for failed query in session {session_id}")
    return jsonify({"removed": removed})


@app.route("/query/stop", methods=["POST"])
def stop_query_agent():
    """Signals the agent to stop processing for the given session."""
    data = request.get_json()
    if not data or "session_id" not in data:
        return jsonify({"error": "Missing 'session_id' field"}), 400

    session_id = data["session_id"]
    interrupt_agent(session_id)
    return jsonify({"message": f"Interrupt signaled for session {session_id}"})


@app.route("/ingest-progress/<session_id>", methods=["GET"])
def ingest_progress(session_id):
    """Streams ingestion progress for a specific session."""
    def generate():
        last_progress = None
        while True:
            sess_col = mongo.get_sessions_collection()
            if sess_col is None:
                yield f"data: {{\"error\": \"DB not connected\"}}\n\n"
                break
            
            doc = sess_col.find_one({"session_id": session_id}, {"ingestion_progress": 1})
            if not doc or "ingestion_progress" not in doc:
                # If progress not yet initialized, just wait
                time.sleep(1)
                continue
            
            progress = doc["ingestion_progress"]
            
            # Only send if progress changed
            if progress != last_progress:
                yield f"data: {json.dumps(progress)}\n\n"
                last_progress = progress
            
            if progress.get("phase") in ["complete", "failed"]:
                break
                
            time.sleep(0.5)

    return Response(generate(), content_type='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
        'Connection': 'keep-alive'
    })


@app.route("/ingest", methods=["POST"])
def ingest_document():
    """Ingests a document. If file is a PDF, routes to the PDF parser. Runs processing in background."""
    file = request.files.get("file")
    raw_text = request.form.get("raw_text")
    session_id = request.form.get("session_id")
    source_filename = request.form.get("filename", "")

    if not file and not raw_text:
        return jsonify({"error": "Must provide either a file or raw_text"}), 400

    if not session_id:
        session_id = memory.create_conversation()

    temp_path = None
    if file:
        temp_path = f"/tmp/{file.filename}"
        file.save(temp_path)

    # Start ingestion in a daemon thread so it runs in background
    thread = threading.Thread(target=start_ingession, args=(temp_path, raw_text, session_id, source_filename))
    thread.daemon = True
    thread.start()

    return jsonify({"message": "Document accepted. Ingestion running in the background.", "session_id": session_id})


@app.route("/sessions", methods=["GET"])
def get_sessions():
    collection = mongo.get_sessions_collection()
    if collection is None:
        return jsonify({"error": "DB not connected"}), 503

    # Sort descending by upload_time
    cursor = collection.find({}, {"_id": 0}).sort("upload_time", -1)
    sessions = []
    for s in cursor:
        sessions.append(s)
    return jsonify(sessions)


@app.route("/messages/<session_id>", methods=["GET"])
def get_messages(session_id):
    """Fetches the conversation history for a specific session directly from the messages collection."""
    chat_logs = memory.get_history(session_id)
    return jsonify(chat_logs)


@app.route("/vectors/<session_id>", methods=["GET"])
def get_vectors(session_id):
    """Returns all vector doc texts for a session (for reference panel)."""
    docs = session_cache.get_vector_docs(session_id)
    if docs is None:
        vector_col = mongo.get_vector_collection()
        if vector_col is None:
            return jsonify({"error": "DB not connected"}), 503
        docs = list(vector_col.find(
            {"session_id": {"$in": [session_id]}},
            {"text": 1, "chapter": 1, "parent_chapter_index": 1, "_id": 0}
        ))
    cleaned = [{"text": d.get("text", ""), "chapter": d.get("chapter", ""), "parent_chapter_index": d.get("parent_chapter_index", 0)} for d in docs]
    return jsonify(cleaned)


@app.route("/messages-analytics", methods=["GET"])
def get_messages_analytics():
    """Retrieves message-level analytics (agent messages with answer times and model names).

    Query params:
    - session_id: Filter by session (default: 'all')
    - from: ISO date string (optional)
    - to: ISO date string (optional)

    Returns agent messages where is_hidden=false with model_name and total_time.
    """
    messages_col = mongo.get_messages_collection()
    if messages_col is None:
        return jsonify({"error": "DB not connected"}), 503

    session_id_param = request.args.get("session_id", "all")
    from_date = request.args.get("from")
    to_date = request.args.get("to")

    # Build query filter
    query_filter = {
        "role": "agent",
        "is_hidden": False
    }

    if session_id_param != "all" and session_id_param:
        query_filter["session_id"] = session_id_param

    if from_date or to_date:
        query_filter["timestamp"] = {}
        if from_date:
            query_filter["timestamp"]["$gte"] = from_date
        if to_date:
            query_filter["timestamp"]["$lte"] = to_date

    # Fetch all matching messages
    try:
        raw_docs = list(messages_col.find(query_filter, {"_id": 0}).sort("timestamp", -1))
    except Exception as e:
        logger.error(f"Messages analytics query failed: {e}")
        return jsonify({"error": str(e)}), 500

    # Extract unique models and sessions
    models = list(set(d.get("model_name") for d in raw_docs if d.get("model_name")))
    sessions = list(set(d.get("session_id") for d in raw_docs if d.get("session_id")))

    return jsonify({
        "raw": raw_docs,
        "models": sorted(models),
        "sessions": sorted(sessions),
        "total_records": len(raw_docs)
    })


@app.route("/analytics", methods=["GET"])
def get_analytics():
    """Retrieves analytics data from MongoDB with optional filtering.

    Query params:
    - session_id: Filter by session (default: 'all')
    - from: ISO date string (optional)
    - to: ISO date string (optional)

    Returns aggregated analytics including raw data, session list, and tool names.
    """
    analytics_col = mongo.get_analytics_collection()
    sess_col = mongo.get_sessions_collection()
    if analytics_col is None:
        return jsonify({"error": "DB not connected"}), 503

    session_id_param = request.args.get("session_id", "all")
    from_date = request.args.get("from")
    to_date = request.args.get("to")

    # Build query filter
    query_filter = {}

    if session_id_param != "all" and session_id_param:
        query_filter["session_id"] = session_id_param

    if from_date or to_date:
        query_filter["timestamp"] = {}
        if from_date:
            query_filter["timestamp"]["$gte"] = from_date
        if to_date:
            query_filter["timestamp"]["$lte"] = to_date

    # Fetch all matching analytics
    try:
        raw_docs = list(analytics_col.find(query_filter, {"_id": 0}).sort("timestamp", -1))
    except Exception as e:
        logger.error(f"Analytics query failed: {e}")
        return jsonify({"error": str(e)}), 500

    # Extract unique sessions and tool names
    sessions = list(set(d.get("session_id") for d in raw_docs if d.get("session_id")))
    tool_names = list(set(d.get("tool_name") for d in raw_docs if d.get("tool_name")))

    sess = list(sess_col.find({}, {"session_id": 1, "chat_name":1}))

    session_map = {s['session_id']:s['chat_name'] for s in sess if s.get("chat_name")}

    for d in raw_docs:
        if d.get("tool_name"):
            d['tool_name'] = TOOLS_NAME_MAP[d['tool_name']]

    tool_names = [TOOLS_NAME_MAP[t] for t in tool_names]

    return jsonify({
        "raw": raw_docs,
        "sessions": sorted(sessions),
        "tool_names": sorted(tool_names),
        "total_records": len(raw_docs),
        "session_map": session_map
    })


@app.route("/sessions/<session_id>", methods=["GET", "DELETE"])
def handle_session(session_id):
    logger.info("Step 1")
    if request.method == "GET":
        collection = mongo.get_sessions_collection()
        logger.info("Step 2")
        if collection is None:
            return jsonify({"error": "DB not connected"}), 503
        logger.info("Step 3")
        doc = collection.find_one({"session_id": session_id}, {"_id": 0})
        if not doc:
            return jsonify({"error": "Session not found"}), 404
        logger.info("Step 4")
        # Start background cache load
        thread = threading.Thread(target=cache_session_docs_background, args=(session_id,))
        thread.daemon = True
        thread.start()
        logger.info("Step 5")
        return jsonify(doc)

    elif request.method == "DELETE":
        sess_col = mongo.get_sessions_collection()
        doc_col = mongo.get_vector_collection()
        msg_col = mongo.get_messages_collection()

        if sess_col is None or doc_col is None or msg_col is None:
            return jsonify({"error": "DB not connected"}), 503

        # 1. Delete session metadata
        sess_result = sess_col.delete_one({"session_id": session_id})

        # 2. Delete standalone messages
        msg_result = msg_col.delete_many({"session_id": session_id})

        # 2. Remove session_id from associated document chunks (don't delete document)
        doc_result = doc_col.update_many({"session_id": session_id}, {"$pull": {"session_id": session_id}})
        
        # 3. Invalidate cache
        session_cache.invalidate(session_id)
        
        logger.info(f"Deleted session {session_id}. Dissociated {doc_result.modified_count} document chunks. Cache invalidated.")

        if sess_result.deleted_count == 0:
            return jsonify({"error": "Session not found"}), 404

        return jsonify({"message": "Session deleted successfully"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)