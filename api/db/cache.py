import threading
import logging
import numpy as np

logger = logging.getLogger(__name__)

class SessionCache:
    """Simple in-memory cache for session-specific document and metadata results."""
    def __init__(self):
        self._vector_docs = {}     # session_id -> list of docs
        self._vector_embeddings = {} # session_id -> array of embeddings
        self._metadata = {}        # session_id -> list of metadata objects
        self._lock = threading.Lock()

    def get_vector_docs(self, session_id: str):
        with self._lock:
            return self._vector_docs.get(session_id)

    def get_vector_embeddings(self, session_id: str):
        with self._lock:
            return self._vector_embeddings.get(session_id)

    def set_vector_docs(self, session_id: str, docs: list):
        with self._lock:
            logger.info(f"Caching {len(docs)} documents for session: {session_id}")
            self._vector_embeddings[session_id] = np.ascontiguousarray([doc["embedding"] for doc in docs], dtype=np.float32)
            for i, doc in enumerate(docs):
                doc["_index"] = i
                if "embedding" in doc:
                    del doc["embedding"]
            self._vector_docs[session_id] = docs

    def get_metadata(self, session_id: str):
        with self._lock:
            return self._metadata.get(session_id)

    def set_metadata(self, session_id: str, metadata: list):
        with self._lock:
            logger.info(f"Caching metadata for session: {session_id}")
            self._metadata[session_id] = metadata

    def invalidate(self, session_id: str):
        with self._lock:
            logger.info(f"Invalidating cache for session: {session_id}")
            self._vector_docs.pop(session_id, None)
            self._vector_embeddings.pop(session_id, None)
            self._metadata.pop(session_id, None)

    def clear(self):
        with self._lock:
            self._vector_docs.clear()
            self._vector_embeddings.clear()
            self._metadata.clear()

# Singleton instance
session_cache = SessionCache()
