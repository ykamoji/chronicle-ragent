import threading
import hashlib
import time
from api.ingestion.extractor import extract_metadata
from api.ingestion.parser import chunk_text
from concurrent.futures import ThreadPoolExecutor, as_completed
from api.ingestion.RateLimiter import RateLimiter

MAX_WORKERS = 3  # Tune based on API limits
MAX_RETRIES = 3
CONCURRENCY_LIMIT = 3  # Usually <= MAX_WORKERS
RATE_LIMIT_PER_MIN = 8

rate_semaphore_extractor = threading.Semaphore(CONCURRENCY_LIMIT)
progress_lock_extractor = threading.Lock()
current_progress = 0

rate_limiter_extractor = RateLimiter(RATE_LIMIT_PER_MIN, 60)


def cleanup_session_data(session_id, vector_col, sess_col, logger):
    """Remove all metadata and vector associations for a failed session."""
    logger.info(f"Cleaning up data for session {session_id} due to ingestion failure.")
    sess_col.delete_one({"session_id": session_id})
    vector_col.update_many({"session_id": session_id}, {"$pull": {"session_id": session_id}})


def copy_metadata(c_hash, existing, i, sess_col, session_id, vector_col, logger):
    # Copy metadata from existing session if available
    chapter_name = existing.get("chapter")
    existing_sessions = existing.get("session_id", [])

    logger.info(f"Chapter {chapter_name} already in DB. Associating with current session.")
    res = vector_col.update_many({"chapter_hash": c_hash}, {"$addToSet": {"session_id": session_id}})

    if chapter_name and existing_sessions:
        # Find a session that has this chapter in its metadata and pull only that record
        source_sess_doc = sess_col.find_one({
            "session_id": {"$in": existing_sessions},
            "metadata.chapter": chapter_name
        }, {"metadata.$": 1, "_id": 0})

        if source_sess_doc and "metadata" in source_sess_doc:
            item_to_copy = source_sess_doc["metadata"][0]
            # Push to the current session
            sess_col.update_one({"session_id": session_id}, {"$push": {"metadata": item_to_copy}})
            logger.info(f"Copied metadata for '{chapter_name}' from an existing session.")

    return res.modified_count, existing_sessions


def extract_metadata_invocation(chapter_text, i, sess_col, session_id, vector_col, logger):
    metadata = {"summary": "", "chapter": "Unknown", "characters": [], "pov" : ""}
    success = False
    for attempt in range(3):
        try:
            # Enforce rate limit (8/min)
            rate_limiter_extractor.acquire()

            # Enforce concurrency limit
            with rate_semaphore_extractor:
                metadata, success = extract_metadata(chapter_text)

            if success: break

        except Exception as e:
            logger.warning(f"Embedding failed (Attempt {attempt + 1}/{MAX_RETRIES}) for chapter {i}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 * (attempt + 1))  # exponential backoff

    if not success:
        cleanup_session_data(session_id, vector_col, sess_col, logger)
        raise Exception(f"Metadata extraction failed for chapter {i} after 3 attempts.")

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

    logger.info(f"Metadata extracted for chapter {metadata.get('chapter', 'Unknown')}")
    return metadata


def create_vectors(c_hash, chapter_text, i, sess_col, session_id, vector_col, logger):

    metadata = extract_metadata_invocation(chapter_text, i, sess_col, session_id, vector_col, logger)
    ## Removing the cleaned header and keeping text only.
    chapter_text = "\n\n".join(chapter_text.split("\n\n")[1:])
    sub_chunks = chunk_text(chapter_text, target_tokens=800)
    docs = [
        {
            "text": sub_chunk,
            "embedding": None,
            "chapter": metadata.get("chapter", "Unknown"),
            "parent_chapter_index": j,
            "chapter_hash": c_hash,
            "pov": metadata.get("POV") if metadata.get("POV") != "Unknown" else "",
            "session_id": [session_id],
        }
        for j, sub_chunk in enumerate(sub_chunks)
    ]
    result = vector_col.insert_many(docs, ordered=False)

    inserts = len(result.inserted_ids)

    logger.info(f"Created {inserts} vectors for chapter {metadata.get('chapter', 'Unknown')}")

    return inserts


def update_progress(sess_col, session_id):
    global current_progress

    with progress_lock_extractor:
        current_progress += 1
        sess_col.update_one(
            {"session_id": session_id},
            {"$set": {"ingestion_progress.current": current_progress}}
        )


def process_chapter(i, chapter_text, session_id, vector_col, sess_col, logger):
    try:
        c_hash = hashlib.sha256(chapter_text.encode("utf-8")).hexdigest()
        existing = vector_col.find_one({"chapter_hash": c_hash}, {"session_id": 1, "chapter": 1, "_id": 0}, )
        if existing:
            embeddings_count, existing_sessions = copy_metadata(c_hash, existing, i, sess_col, session_id, vector_col, logger)
            if not existing_sessions:
                extract_metadata_invocation(chapter_text, i, sess_col, session_id, vector_col, logger)

            update_progress(sess_col, session_id)
            return {
                "chapter_hash": c_hash,
                "embeddings_added": embeddings_count,
            }

        embeddings_count = create_vectors(c_hash, chapter_text, i, sess_col, session_id, vector_col, logger)

        update_progress(sess_col, session_id)

        return {
            "chapter_hash": c_hash,
            "embeddings_added": embeddings_count,
        }
    except Exception as e:
        logger.error(f"Error processing chapter {i}: {e}")
        raise


# ==============================
# PARALLEL EXTRACTION EXECUTION
# ==============================
def parallel_extractor(chapters, sess_col, session_id, vector_col, logger):
    chapter_hashes = []
    embeddings_count = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(process_chapter, i, chapter, session_id, vector_col, sess_col, logger)
            for i, chapter in enumerate(chapters)
        ]

        for future in as_completed(futures):
            try:
                result = future.result()

                # Aggregate safely (single-thread here)
                chapter_hashes.append(result["chapter_hash"])
                embeddings_count += result["embeddings_added"]

            except Exception as e:
                logger.error(f"Ingestion failed: {e}")
                cleanup_session_data(session_id, vector_col, sess_col, logger)
                raise

    logger.info("Ingestion completed successfully")

    return chapter_hashes, embeddings_count
