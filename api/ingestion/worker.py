from api.ingestion.text_metadata import extract_rag_stats
import os
from dotenv import load_dotenv
load_dotenv()
import logging
import time
import hashlib
from api.db.mongo import mongo
from api.ingestion.embedder import get_embedding
from api.ingestion.parser import extract_text_from_pdf, chunk_by_chapter
from api.ingestion.extractExec import parallel_extractor, copy_metadata, extract_metadata_invocation, create_vectors
from api.ingestion.embedExec import embed_missing_docs_parallel
from api.config.settings import app_settings

logger = logging.getLogger(__name__)

def sequential_extractor(chapters, sess_col, session_id, vector_col):
    chapter_hashes = []
    total_embeddings_count = 0
    # Phase 1: Metadata Extraction
    for i, chapter_text in enumerate(chapters):
        try:
            c_hash = hashlib.sha256(chapter_text.encode('utf-8')).hexdigest()
            chapter_hashes.append(c_hash)

            existing = vector_col.find_one({"chapter_hash": c_hash},  {"session_id": 1, "chapter": 1, "_id": 0})
            if existing:
                embeddings_count, existing_sessions = copy_metadata(c_hash, existing, i, sess_col, session_id, vector_col, logger)
                total_embeddings_count += embeddings_count
                if not existing_sessions:
                    extract_metadata_invocation(chapter_text, i, sess_col, session_id, vector_col, logger)
                    time.sleep(app_settings.get_delay())

                # We don't skip entirely; we still want to check if embeddings are needed in Phase 2
                continue

            create_vectors(c_hash, chapter_text, i, sess_col, session_id, vector_col, logger)

            # Update current progress
            sess_col.update_one({"session_id": session_id}, {"$set": {"ingestion_progress.current": i + 1}})
            # logger.info(f"Metadata extracted for chapter {i}.")
            time.sleep(app_settings.get_delay())
        except Exception as e:
            logger.error(f"Failed processing chapter {i}: {e}")
    return chapter_hashes, total_embeddings_count


def sequence_embed_docs(missing_docs, session_id, sess_col, vector_col):
    # logger.info(f"Starting sequence embedding for {len(missing_docs)} documents...")

    for idx, doc in enumerate(missing_docs):
        # Update current progress
        sess_col.update_one({"session_id": session_id}, {"$set": {"ingestion_progress.current": idx + 1}})

        doc_id = doc["_id"]
        text_to_embed = doc["text"]
        success = False
        text_to_embed = f"[{doc['chapter']} | POV : {doc['pov']}] " + text_to_embed

        logger.info(f"Embedding {text_to_embed[:100]}...")
        for attempt in range(3):
            try:
                emb = get_embedding(text_to_embed)
                vector_col.update_one({"_id": doc_id}, {"$set": {"embedding": emb}})
                success = True
                break
            except Exception as e:
                logger.warning(f"Embedding failed (Attempt {attempt + 1}/3) for doc {doc_id}: {e}")
                time.sleep(2)

        if not success:
            logger.error(f"Failed to generate embedding for doc {doc_id} after 3 attempts.")

        # logger.info(f"Embedding generated for chunk {idx + 1}")

        time.sleep(5)  # Reduced for better demo


def root_embedder(chapter_hashes, embeddings_count, sess_col, session_id, vector_col):
    # Phase 2: Embedding Generation & Retries
    logger.info("Phase 2: Generating embeddings...")
    missing_docs = list(vector_col.find({"chapter_hash": {"$in": chapter_hashes}, "embedding": None}))
    total_embeddings = len(missing_docs)
    # Switch to embedding phase
    if total_embeddings == 0:
        sess_col.update_one({"session_id": session_id}, {
            "$set": {"ingestion_progress": {"phase": "embedding", "current": 0, "total": embeddings_count}}})
        for idx in range(embeddings_count):
            sess_col.update_one({"session_id": session_id}, {"$set": {"ingestion_progress.current": idx + 1}})
            # logger.info(f"Embedding generated for chunk {idx + 1}")
            # time.sleep(30)
    else:
        sess_col.update_one({"session_id": session_id}, {
            "$set": {"ingestion_progress": {"phase": "embedding", "current": 0, "total": total_embeddings}}})
        # logger.info(f"Found {total_embeddings} chunks needing embeddings.")

        # Choose embedding strategy based on settings
        if app_settings.get_embedder_parallel():
            logger.info("Parallel Embedding Execution.")
            embed_missing_docs_parallel(missing_docs, session_id, sess_col, vector_col, logger)
        else:
            logger.info("Sequential Embedding Execution.")
            sequence_embed_docs(missing_docs, session_id, sess_col, vector_col)


def process_file_background(text_content: str, session_id: str):
    """Background task to chunk, embed, and store document segments."""

    vector_col = mongo.get_vector_collection()
    sess_col = mongo.get_sessions_collection()
    if vector_col is None or sess_col is None:
        logger.error("MongoDB not connected. Aborting ingestion.")
        return

    try:
        # Start extraction phase
        chapters = chunk_by_chapter(text_content)
        total_chapters = len(chapters)
        # logger.info(f"Text parsed into {total_chapters} chapters for metadata extraction.")

        rag_stats = extract_rag_stats(chapters)

        sess_col.update_one({"session_id": session_id},
                            {"$set":
                                 {
                                    "stats": rag_stats,
                                    "ingestion_progress":
                                        {"phase": "extraction", "current": 0, "total": total_chapters}
                                 }
                            })

        if app_settings.get_embedder_parallel():
            logger.info("Parallel Extraction Execution.")
            chapter_hashes, embeddings_count = parallel_extractor(chapters, sess_col, session_id, vector_col, logger)
        else:
            logger.info("Sequential Extraction Execution.")
            chapter_hashes, embeddings_count = sequential_extractor(chapters, sess_col, session_id, vector_col)

        root_embedder(chapter_hashes, embeddings_count, sess_col, session_id, vector_col)

        # Finalize progress
        sess_col.update_one({"session_id": session_id}, {"$set": {"ingestion_progress.phase": "complete"}})
        
        logger.info("Ingestion complete.")
    except Exception as e:
        logger.error(f"Ingestion pipeline failed: {e}")
        sess_col.update_one({"session_id": session_id},
                            {"$set": {"ingestion_progress.phase": "failed", "error": str(e)}})


def start_ingession(temp_path, raw_text, session_id, source_filename):

    try:
       
        logger.info(f"Starting ingestion for session {session_id}")

        # Save source filename to session document if provided
        if source_filename:
            sess_col = mongo.get_sessions_collection()
            if sess_col is not None:
                sess_col.update_one(
                    {"session_id": session_id},
                    {"$set": {"source_filename": source_filename}},
                    upsert=True
                )

        text_to_process = ""

        if temp_path:
            if temp_path.endswith('.pdf'):
                text_to_process = extract_text_from_pdf(temp_path)
            elif temp_path.endswith('.txt'):
                with open(temp_path, 'r') as f:
                    text_to_process = f.read()
            else:
                logger.error("Unsupported file format. Use .pdf or .txt")
        
        if raw_text:
            text_to_process += "\n\n" + raw_text

        text_to_process = text_to_process.strip()

        if not text_to_process:
            return logger.error("Extracted text is empty.")

        process_file_background(text_to_process, session_id)

        os.remove(temp_path)

    except Exception as e:
        logger.error(f"Ingestion pipeline failed: {e}")