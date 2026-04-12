from dotenv import load_dotenv
load_dotenv()
import time
import json
import hashlib
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from api.agent.orchestrator import run_agent_stream
from api.agent.memory import memory
from api.ingestion.parser import extract_text_from_pdf, chunk_text, chunk_by_chapter
from api.ingestion.extractor import extract_metadata
from api.ingestion.embedder import get_embedding
from api.db.mongo import mongo
from api.db.cache import session_cache
from api.config.settings import app_settings
import logging
import os
import threading
from tqdm import tqdm

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
    return jsonify({"status": "healthy", "mongo_connected": mongo.client is not None})


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


def process_file_background(text_content: str, session_id: str):
    """Background task to chunk, embed, and store document segments."""
    try:
        vector_col = mongo.get_vector_collection()
        sess_col = mongo.get_sessions_collection()
        if vector_col is None or sess_col is None:
            logger.error("MongoDB not connected. Aborting ingestion.")
            return

        # Start extraction phase
        sess_col.update_one({"session_id": session_id}, {"$set": {"ingestion_progress": {"phase": "extraction", "current": 0, "total": 0}}})

        chapters = chunk_by_chapter(text_content)
        total_chapters = len(chapters)
        logger.info(f"Text parsed into {total_chapters} chapters for metadata extraction.")

        # Update total chapters
        sess_col.update_one({"session_id": session_id}, {"$set": {"ingestion_progress.total": total_chapters}})

        chapter_hashes = []

        # Phase 1: Metadata Extraction
        for i, chapter_text in enumerate(tqdm(chapters, desc="Extracting Metadata")):
            # Update current progress
            sess_col.update_one({"session_id": session_id}, {"$set": {"ingestion_progress.current": i + 1}})

            c_hash = hashlib.sha256(chapter_text.encode('utf-8')).hexdigest()
            chapter_hashes.append(c_hash)
            
            existing = vector_col.find_one({"chapter_hash": c_hash})
            if existing:
                logger.info(f"Chapter {i+1} already in DB. Associating with current session.")
                vector_col.update_many({"chapter_hash": c_hash}, {"$addToSet": {"session_id": session_id}})
                
                # Copy metadata from existing session if available
                chapter_name = existing.get("chapter")
                existing_sessions = existing.get("session_id", [])
                if chapter_name and existing_sessions:
                    # Find a session that has this chapter in its metadata and pull only that record
                    source_sess_doc = sess_col.find_one({
                        "session_id": {"$in": existing_sessions},
                        "metadata.chapter": chapter_name
                    }, {"metadata.$": 1})
                    
                    if source_sess_doc and "metadata" in source_sess_doc:
                        item_to_copy = source_sess_doc["metadata"][0]
                        # Push to the current session
                        sess_col.update_one({"session_id": session_id}, {"$push": {"metadata": item_to_copy}})
                        logger.info(f"Copied metadata for '{chapter_name}' from an existing session.")

                if not existing_sessions:
                    metadata = extract_metadata(chapter_text)
                    chapter_summary = metadata.get("summary", "")
                    if chapter_summary:
                        sess_col.update_one({"session_id": session_id}, 
                        {"$push": 
                            {"metadata": {
                                "chapter": metadata.get("chapter", "Unknown"), 
                                "summary": chapter_summary,
                                "characters": metadata.get("characters", [])
                                }
                            }
                        })
                    time.sleep(10)
                    
                # We don't skip entirely; we still want to check if embeddings are needed in Phase 2
                continue

            try:
                metadata = extract_metadata(chapter_text)
                
                chapter_summary = metadata.get("summary", "")
                if chapter_summary:
                    sess_col.update_one({"session_id": session_id}, 
                    {"$push": 
                        {"metadata": {
                            "chapter": metadata.get("chapter", "Unknown"), 
                            "summary": chapter_summary,
                            "characters": metadata.get("characters", [])
                            }
                        }
                    })

                sub_chunks = chunk_text(chapter_text, target_tokens=500)
                
                for j, sub_chunk in enumerate(sub_chunks):
                    doc = {
                        "text": sub_chunk,
                        "embedding": None,
                        "chapter": metadata.get("chapter", "Unknown"),
                        "parent_chapter_index": j,
                        "chapter_hash": c_hash,
                        "session_id": [session_id]
                    }
                    vector_col.insert_one(doc)
                
                time.sleep(10)
            except Exception as e:
                logger.error(f"Failed processing chapter {i}: {e}")

        # Phase 2: Embedding Generation & Retries
        logger.info("Phase 2: Generating embeddings...")
        missing_docs = list(vector_col.find({"chapter_hash": {"$in": chapter_hashes}, "embedding": None}))
        total_embeddings = len(missing_docs)
        logger.info(f"Found {total_embeddings} chunks needing embeddings.")
        
        # Switch to embedding phase
        sess_col.update_one({"session_id": session_id}, {"$set": {"ingestion_progress": {"phase": "embedding", "current": 0, "total": total_embeddings}}})

        if total_embeddings == 0:
             sess_col.update_one({"session_id": session_id}, {"$set": {"ingestion_progress.phase": "complete"}})
        else:
            for idx, doc in enumerate(tqdm(missing_docs, desc="Generating Embeddings")):
                # Update current progress
                sess_col.update_one({"session_id": session_id}, {"$set": {"ingestion_progress.current": idx + 1}})

                doc_id = doc["_id"]
                text_to_embed = doc["text"]
                success = False
                for attempt in range(3):
                    try:
                        emb = get_embedding(text_to_embed)
                        vector_col.update_one({"_id": doc_id}, {"$set": {"embedding": emb}})
                        success = True
                        break
                    except Exception as e:
                        logger.warning(f"Embedding failed (Attempt {attempt+1}/3) for doc {doc_id}: {e}")
                        time.sleep(2)
                
                if not success:
                    logger.error(f"Failed to generate embedding for doc {doc_id} after 3 attempts.")
                
                time.sleep(10) # Reduced for better demo
            
        # Finalize progress
        sess_col.update_one({"session_id": session_id}, {"$set": {"ingestion_progress.phase": "complete"}})

        # Invalidate cache so the next query pulls fresh data from MongoDB
        session_cache.invalidate(session_id)
        logger.info("Ingestion complete. Cache invalidated.")
    except Exception as e:
        logger.error(f"Ingestion pipeline failed: {e}")
        sess_col.update_one({"session_id": session_id}, {"$set": {"ingestion_progress.phase": "failed", "error": str(e)}})


@app.route("/ingest", methods=["POST"])
def ingest_document():
    """Ingests a document. If file is a PDF, routes to the PDF parser. Runs processing in background."""
    file = request.files.get("file")
    raw_text = request.form.get("raw_text")
    session_id = request.form.get("session_id")

    if not file and not raw_text:
        return jsonify({"error": "Must provide either a file or raw_text"}), 400

    if not session_id:
        session_id = memory.create_conversation()

    text_to_process = ""

    if file:
        if file.filename.endswith('.pdf'):
            # Save temporary file to parse
            temp_path = f"/tmp/{file.filename}"
            file.save(temp_path)

            text_to_process = extract_text_from_pdf(temp_path)
            os.remove(temp_path)
        elif file.filename.endswith('.txt'):
            content = file.read()
            text_to_process = content.decode('utf-8')
        else:
            return jsonify({"error": "Unsupported file format. Use .pdf or .txt"}), 400

    if raw_text:
        text_to_process += "\n\n" + raw_text

    text_to_process = text_to_process.strip()
    if not text_to_process:
        return jsonify({"error": "Extracted text is empty."}), 400

    # Start ingestion in a daemon thread so it runs in background
    thread = threading.Thread(target=process_file_background, args=(text_to_process, session_id))
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

def cache_session_docs_background(session_id: str):
    """Background task to load vector docs into cache."""
    try:
        vector_col = mongo.get_vector_collection()
        if vector_col is None:
            return
            
        # Skip if already cached
        if session_cache.get_vector_docs(session_id) is not None:
            return
             
        cursor = vector_col.find(
            {"session_id": {"$in": [session_id]}},
            {"embedding": 1, "text": 1, "chapter": 1, "_id": 0}
        )
        docs = list(cursor)
        session_cache.set_vector_docs(session_id, docs)
        logger.info(f"Background cache loaded {len(docs)} docs for session {session_id}")
    except Exception as e:
        logger.error(f"Failed to background cache session {session_id}: {e}")

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


@app.route("/sessions/<session_id>", methods=["GET", "DELETE"])
def handle_session(session_id):
    if request.method == "GET":
        collection = mongo.get_sessions_collection()
        if collection is None:
            return jsonify({"error": "DB not connected"}), 503

        doc = collection.find_one({"session_id": session_id}, {"_id": 0})
        if not doc:
            return jsonify({"error": "Session not found"}), 404

        # Start background cache load
        thread = threading.Thread(target=cache_session_docs_background, args=(session_id,))
        thread.daemon = True
        thread.start()

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
    app.run(host="127.0.0.1", port=8000, debug=True)