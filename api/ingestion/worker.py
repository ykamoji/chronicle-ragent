import os
from dotenv import load_dotenv
load_dotenv()
import logging
import time
import hashlib
from api.ingestion.extractor import extract_metadata
from api.ingestion.embedder import get_embedding
from api.ingestion.parser import extract_text_from_pdf, chunk_text, chunk_by_chapter
from api.db.mongo import mongo
from api.config.settings import app_settings

logger = logging.getLogger(__name__)

def cleanup_session_data(session_id, vector_col, sess_col):
    """Remove all metadata and vector associations for a failed session."""
    logger.info(f"Cleaning up data for session {session_id} due to ingestion failure.")
    sess_col.delete_one({"session_id": session_id})
    vector_col.update_many({"session_id": session_id}, {"$pull": {"session_id": session_id}})


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

        embeddings_count = 0

        # Phase 1: Metadata Extraction
        for i, chapter_text in enumerate(chapters):
            # Update current progress
            sess_col.update_one({"session_id": session_id}, {"$set": {"ingestion_progress.current": i + 1}})

            c_hash = hashlib.sha256(chapter_text.encode('utf-8')).hexdigest()
            chapter_hashes.append(c_hash)
            
            existing = vector_col.find_one({"chapter_hash": c_hash})
            if existing:
                logger.info(f"Chapter {i+1} already in DB. Associating with current session.")
                res = vector_col.update_many({"chapter_hash": c_hash}, {"$addToSet": {"session_id": session_id}})
                embeddings_count += res.modified_count
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
                    metadata = {"summary": "", "chapter": "Unknown", "characters": []}
                    success = False
                    for attempt in range(3):
                        metadata, success = extract_metadata(chapter_text)
                        if success:
                            break
                        logger.warning(f"Metadata extraction failed (Attempt {attempt+1}/3) for chapter {i+1}. Retrying in 5s...")
                        time.sleep(5)
                    
                    if not success:
                        cleanup_session_data(session_id, vector_col, sess_col)
                        raise Exception(f"Metadata extraction failed for chapter {i+1} after 3 attempts.")
                    
                    logger.info(f"Metadata extracted for chapter {i+1}")

                    chapter_summary = metadata.get("summary", "")
                    if chapter_summary:
                        sess_col.update_one({"session_id": session_id}, 
                        {"$push": 
                            {"metadata": {
                                "chapter": metadata.get("chapter", "Unknown"), 
                                "summary": chapter_summary,
                                "characters": metadata.get("characters", []),
                                "pov": metadata.get("POV") if metadata.get("POV") != 'Unknown' else ""
                                }
                            }
                        })
                    time.sleep(app_settings.get_delay())
                    
                # We don't skip entirely; we still want to check if embeddings are needed in Phase 2
                continue

            try:
                success = False
                for attempt in range(3):
                    metadata, success = extract_metadata(chapter_text)
                    if success:
                        break
                    logger.warning(f"Metadata extraction failed (Attempt {attempt+1}/3) for chapter {i+1}. Retrying in 5s...")
                    time.sleep(5)

                if not success:
                    cleanup_session_data(session_id, vector_col, sess_col)
                    raise Exception(f"Metadata extraction failed for chapter {i+1} after 3 attempts.")

                # logger.info(f"Metadata extracted: {metadata}")

                logger.info(f"Metadata extracted for chapter {i+1}")
                
                chapter_summary = metadata.get("summary", "")
                if chapter_summary:
                    sess_col.update_one({"session_id": session_id}, 
                    {"$push": 
                        {"metadata": {
                            "chapter": metadata.get("chapter", "Unknown"), 
                            "summary": chapter_summary,
                            "characters": metadata.get("characters", []),
                            "pov": metadata.get("POV") if metadata.get("POV") != 'Unknown' else ""
                            }
                        }
                    })

                sub_chunks = chunk_text(chapter_text, target_tokens=800)
                
                for j, sub_chunk in enumerate(sub_chunks):
                    doc = {
                        "text": sub_chunk,
                        "embedding": None,
                        "chapter": metadata.get("chapter", "Unknown"),
                        "parent_chapter_index": j,
                        "chapter_hash": c_hash,
                        "pov": metadata.get("POV") if metadata.get("POV") != 'Unknown' else "",
                        "session_id": [session_id]
                    }
                    vector_col.insert_one(doc)
                
                time.sleep(app_settings.get_delay())
            except Exception as e:
                logger.error(f"Failed processing chapter {i}: {e}")

        # Phase 2: Embedding Generation & Retries
        logger.info("Phase 2: Generating embeddings...")
        missing_docs = list(vector_col.find({"chapter_hash": {"$in": chapter_hashes}, "embedding": None}))
        total_embeddings = len(missing_docs)
        
        # Switch to embedding phase

        if total_embeddings == 0:
            sess_col.update_one({"session_id": session_id}, {"$set": {"ingestion_progress": {"phase": "embedding", "current": 0, "total": embeddings_count}}})
            for idx in range(embeddings_count):
                sess_col.update_one({"session_id": session_id}, {"$set": {"ingestion_progress.current": idx + 1}})
                # logger.info(f"Embedding generated for chunk {idx+1}")
                time.sleep(30)
        else:
            sess_col.update_one({"session_id": session_id}, {"$set": {"ingestion_progress": {"phase": "embedding", "current": 0, "total": total_embeddings}}})
            logger.info(f"Found {total_embeddings} chunks needing embeddings.")

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
                        logger.warning(f"Embedding failed (Attempt {attempt+1}/3) for doc {doc_id}: {e}")
                        time.sleep(2)
                
                if not success:
                    logger.error(f"Failed to generate embedding for doc {doc_id} after 3 attempts.")

                logger.info(f"Embedding generated for chunk {idx+1}")
                
                time.sleep(5) # Reduced for better demo
            
        # Finalize progress
        sess_col.update_one({"session_id": session_id}, {"$set": {"ingestion_progress.phase": "complete"}})
        logger.info("Ingestion complete.")
    except Exception as e:
        logger.error(f"Ingestion pipeline failed: {e}")
        sess_col.update_one({"session_id": session_id}, {"$set": {"ingestion_progress.phase": "failed", "error": str(e)}})


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
            os.remove(temp_path)
        
        if raw_text:
            text_to_process += "\n\n" + raw_text

        text_to_process = text_to_process.strip()

        if not text_to_process:
            return logger.error("Extracted text is empty.")


        process_file_background(text_to_process, session_id)

    except Exception as e:
        logger.error(f"Ingestion pipeline failed: {e}")