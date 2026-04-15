import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from api.ingestion.embedder import get_embedding


MAX_WORKERS = 3          # Tune based on API limits
MAX_RETRIES = 3
CONCURRENCY_LIMIT = 3          # Usually <= MAX_WORKERS
RATE_LIMIT_PER_MIN = 80

rate_semaphore = threading.Semaphore(CONCURRENCY_LIMIT)
progress_lock = threading.Lock()

# -----------------------------
# RATE LIMITER
# -----------------------------
class RateLimiter:
    def __init__(self, max_calls, period):
        self.max_calls = max_calls
        self.period = period
        self.lock = threading.Lock()
        self.calls = []

    def acquire(self):
        while True:
            with self.lock:
                now = time.time()

                # remove calls older than window
                self.calls = [t for t in self.calls if now - t < self.period]

                if len(self.calls) < self.max_calls:
                    self.calls.append(now)
                    return

                # calculate sleep time
                sleep_time = self.period - (now - self.calls[0])

            time.sleep(sleep_time)

rate_limiter = RateLimiter(RATE_LIMIT_PER_MIN, 60)

# -----------------------------
# EMBEDDING WORKER
# -----------------------------
def embed_and_store(doc, vector_col, logger):
    doc_id = doc["_id"]

    text_to_embed = f"[{doc['chapter']} | POV : {doc['pov']}] {doc['text']}"

    logger.info(f"Embedding {text_to_embed[:100]}...")

    for attempt in range(MAX_RETRIES):
        try:
            # Enforce rate limit (100/min)
            rate_limiter.acquire()

            # Enforce concurrency limit
            with rate_semaphore:
                emb = get_embedding(text_to_embed)

            vector_col.update_one(
                {"_id": doc_id},
                {"$set": {"embedding": emb}}
            )

            return doc_id, True, None

        except Exception as e:
            logger.warning(f"Embedding failed (Attempt {attempt+1}/{MAX_RETRIES}) for doc {doc_id}: {e}")

            if attempt < MAX_RETRIES - 1:
                time.sleep(2 * (attempt + 1))  # exponential backoff

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

    logger.info(f"Starting parallel embedding for {total} documents...")

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
            with progress_lock:
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