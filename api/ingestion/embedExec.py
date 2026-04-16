import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from api.ingestion.RateLimiter import RateLimiter
from api.ingestion.embedder import get_embedding
from api.config.settings import app_settings

MAX_WORKERS = 3          # Tune based on API limits
MAX_RETRIES = 3
CONCURRENCY_LIMIT = 3          # Usually <= MAX_WORKERS

rate_semaphore_embedder = threading.Semaphore(CONCURRENCY_LIMIT)
progress_lock_embedder = threading.Lock()

rate_limiter_embedder = RateLimiter(app_settings.get_embedder_rate_limit(), 60)

# -----------------------------
# EMBEDDING WORKER
# -----------------------------
def embed_and_store(doc, vector_col, logger):
    doc_id = doc["_id"]

    text_to_embed = f"[{doc['chapter']} | POV : {doc['pov']}] {doc['text']}"

    # logger.info(f"Embedding {text_to_embed[:100]}...")

    for attempt in range(MAX_RETRIES):
        try:
            # Enforce rate limit (/min)
            rate_limiter_embedder.max_calls = app_settings.get_embedder_rate_limit()
            rate_limiter_embedder.acquire()

            # Enforce concurrency limit
            with rate_semaphore_embedder:
                emb = get_embedding(text_to_embed)

            vector_col.update_one(
                {"_id": doc_id},
                {"$set": {"embedding": emb}}
            )

            return doc_id, True, None

        except Exception as e:
            logger.warning(f"Embedding failed (Attempt {attempt+1}/{MAX_RETRIES}): {e}")

            if attempt < MAX_RETRIES - 1:
                time.sleep(4 * (attempt + 1))  # exponential backoff

    # Final failure
    vector_col.update_one({"_id": doc_id}, {"$set": {"embedding_status": "failed"}})

    return doc_id, False, f"Failed after {MAX_RETRIES} attempts"


# -----------------------------
# PARALLEL EMBEDDING EXECUTION
# -----------------------------
def embed_missing_docs_parallel(missing_docs, session_id, sess_col, vector_col, logger):
    """Embed missing documents in parallel using multiple threads."""
    total = len(missing_docs)
    completed = 0

    # logger.info(f"Starting parallel embedding for {total} documents...")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_doc = {
            executor.submit(embed_and_store, doc, vector_col, logger): doc
            for doc in missing_docs
        }

        for future in as_completed(future_to_doc):
            doc = future_to_doc[future]
            doc_id = doc["_id"]

            try:
                _, success, err = future.result()

                if not success:
                    logger.error(f"Doc {doc_id}: {err}")

            except Exception as e:
                logger.error(f"Unexpected failure for doc {doc_id}: {e}")

            # Thread-safe progress update
            with progress_lock_embedder:
                completed += 1

                sess_col.update_one(
                    {"session_id": session_id},
                    {
                        "$set": {
                            "ingestion_progress.current": completed,
                            "ingestion_progress.total": total
                        }
                    }
                )