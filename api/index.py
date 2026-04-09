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
import shutil
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


def process_file_background(text_content: str, session_id: str):
    """Background task to chunk, embed, and store document segments."""
    try:
        collection = mongo.get_vector_collection()
        if collection is None:
            logger.error("MongoDB not connected. Aborting ingestion.")
            return

        chapters = chunk_by_chapter(text_content)
        logger.info(f"Text parsed into {len(chapters)} chapters for metadata extraction.")

        chapter_hashes = []

        # Phase 1: Metadata Extraction
        for i, chapter_text in enumerate(tqdm(chapters, desc="Extracting Metadata")):
            c_hash = hashlib.sha256(chapter_text.encode('utf-8')).hexdigest()
            chapter_hashes.append(c_hash)
            
            existing = collection.find_one({"chapter_hash": c_hash})
            if existing:
                logger.info(f"Chapter {i+1} already in DB. Skipping metadata extraction.")
                continue

            try:
                metadata = extract_metadata(chapter_text)
                
                chapter_summary = metadata.get("summary", "")
                if chapter_summary:
                    sess_col = mongo.get_sessions_collection()
                    if sess_col is not None:
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
                        "session_id": session_id
                    }
                    collection.insert_one(doc)
                
                time.sleep(20)
            except Exception as e:
                logger.error(f"Failed processing chapter {i}: {e}")

        # Phase 2: Embedding Generation & Retries
        logger.info("Phase 2: Generating embeddings...")
        missing_docs = list(collection.find({"chapter_hash": {"$in": chapter_hashes}, "embedding": None}))
        logger.info(f"Found {len(missing_docs)} chunks needing embeddings.")
        
        for doc in tqdm(missing_docs, desc="Generating Embeddings"):
            doc_id = doc["_id"]
            text_to_embed = doc["text"]
            success = False
            for attempt in range(3):
                try:
                    emb = get_embedding(text_to_embed)
                    collection.update_one({"_id": doc_id}, {"$set": {"embedding": emb}})
                    success = True
                    break
                except Exception as e:
                    logger.warning(f"Embedding failed (Attempt {attempt+1}/3) for doc {doc_id}: {e}")
                    time.sleep(5)
            
            if not success:
                logger.error(f"Failed to generate embedding for doc {doc_id} after 3 attempts.")
            
            time.sleep(20)
        logger.info("Ingestion complete.")
    except Exception as e:
        logger.error(f"Ingestion pipeline failed: {e}")


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
        
        # 2. Delete associated document chunks
        doc_result = doc_col.delete_many({"session_id": session_id})
        
        logger.info(f"Deleted session {session_id}. Removed {doc_result.deleted_count} document chunks.")
        
        if sess_result.deleted_count == 0:
            return jsonify({"error": "Session not found"}), 404
            
        return jsonify({"message": "Session deleted successfully"})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)