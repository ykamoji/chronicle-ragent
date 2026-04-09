from dotenv import load_dotenv
load_dotenv()
import time
import hashlib
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from api.agent.orchestrator import run_agent_stream
from api.agent.memory import memory
from api.ingestion.parser import extract_text_from_pdf, chunk_text, chunk_by_chapter
from api.ingestion.extractor import extract_metadata
from api.ingestion.embedder import get_embedding
from api.db.mongo import mongo
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

    return Response(generate(), content_type='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
        'Connection': 'keep-alive'
    })


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
                import json
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
                            "summary": chapter_summary
                            }
                        }
                    })

                sub_chunks = chunk_text(chapter_text, target_tokens=500)
                
                for j, sub_chunk in enumerate(sub_chunks):
                    doc = {
                        "text": sub_chunk,
                        "embedding": None,
                        "chapter": metadata.get("chapter", "Unknown"),
                        "characters": metadata.get("characters", []),
                        "parent_chapter_index": i,
                        "chapter_hash": c_hash,
                        "session_id": [session_id]
                    }
                    vector_col.insert_one(doc)
                
                time.sleep(10) # Reduced for better demo, original was 20
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

        logger.info("Ingestion complete.")
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
        s["chat_logs"] = memory.get_history(s["session_id"])
        sessions.append(s)
    return jsonify(sessions)


@app.route("/sessions/<session_id>", methods=["GET", "DELETE"])
def handle_session(session_id):
    if request.method == "GET":
        collection = mongo.get_sessions_collection()
        if collection is None:
            return jsonify({"error": "DB not connected"}), 503

        doc = collection.find_one({"session_id": session_id}, {"_id": 0})
        if not doc:
            return jsonify({"error": "Session not found"}), 404

        doc["chat_logs"] = doc.get("messages", [])

        return jsonify(doc)

    elif request.method == "DELETE":
        sess_col = mongo.get_sessions_collection()
        doc_col = mongo.get_vector_collection()

        if sess_col is None or doc_col is None:
            return jsonify({"error": "DB not connected"}), 503

        # 1. Delete session metadata
        sess_result = sess_col.delete_one({"session_id": session_id})

        # 2. Remove session_id from associated document chunks (don't delete document)
        doc_result = doc_col.update_many({"session_id": session_id}, {"$pull": {"session_id": session_id}})
        
        logger.info(f"Deleted session {session_id}. Dissociated {doc_result.modified_count} document chunks.")

        if sess_result.deleted_count == 0:
            return jsonify({"error": "Session not found"}), 404

        return jsonify({"message": "Session deleted successfully"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)