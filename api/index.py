from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify
from flask_cors import CORS
from api.agent.orchestrator import run_agent
from api.agent.memory import memory
from api.ingestion.parser import extract_text_from_pdf, chunk_text
from api.ingestion.extractor import extract_metadata
from api.ingestion.embedder import get_embedding
from api.db.mongo import mongo
import logging
import os
import shutil
import threading

# Basic Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# Allow CORS from everywhere for Next.js proxy/LAN interaction
CORS(app)

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "mongo_connected": mongo.client is not None})

@app.route("/query", methods=["POST"])
def query_agent():
    """Hits the main ReAct agent with a user query."""
    if not mongo.client:
        return jsonify({"error": "MongoDB is not connected. Agent cannot retrieve data."}), 503
        
    data = request.get_json()
    if not data or "query" not in data:
        return jsonify({"error": "Missing 'query' field in JSON."}), 400
        
    user_query = data.get("query")
    session_id = data.get("session_id")
    
    if not session_id:
        session_id = memory.create_conversation()

    logger.info(f"Starting agent run for session: {session_id}")
    answer = run_agent(session_id, user_query)
    
    return jsonify({"answer": answer, "session_id": session_id})


def process_file_background(text_content: str):
    """Background task to chunk, embed, and store document segments."""
    try:
        # Pymongo isn't strictly thread-safe in complex ops but typical singleton inserts are often fine. 
        # For production robustness, fetching a fresh collection object per thread is safer.
        collection = mongo.get_collection()
        if collection is None:
            logger.error("MongoDB not connected. Aborting ingestion.")
            return

        chunks = chunk_text(text_content, target_tokens=400)
        logger.info(f"Text parsed into {len(chunks)} chunks.")

        for i, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {i+1}/{len(chunks)}...")
            try:
                metadata = extract_metadata(chunk)
                embedding = get_embedding(chunk)
                
                doc = {
                    "text": chunk,
                    "embedding": embedding,
                    "summary": metadata.get("summary", ""),
                    "chapter": metadata.get("chapter", "Unknown"),
                    "characters": metadata.get("characters", []),
                }
                collection.insert_one(doc)
            except Exception as e:
                logger.error(f"Failed processing chunk {i}: {e}")

        logger.info("Ingestion complete.")
    except Exception as e:
        logger.error(f"Ingestion pipeline failed: {e}")


@app.route("/ingest", methods=["POST"])
def ingest_document():
    """Ingests a document. If file is a PDF, routes to the PDF parser. Runs processing in background."""
    file = request.files.get("file")
    raw_text = request.form.get("raw_text")

    if not file and not raw_text:
        return jsonify({"error": "Must provide either a file or raw_text"}), 400

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
    thread = threading.Thread(target=process_file_background, args=(text_to_process,))
    thread.daemon = True
    thread.start()
    
    return jsonify({"message": "Document accepted. Ingestion running in the background."})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
