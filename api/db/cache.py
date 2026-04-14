import threading
import logging
from dotenv import load_dotenv
load_dotenv()
from api.db.mongo import mongo

logger = logging.getLogger(__name__)

class SessionCache:
    """Simple in-memory cache for session-specific document and metadata results."""
    def __init__(self):
        self._vector_docs = {}     # session_id -> list of docs
        self._metadata = {}        # session_id -> list of metadata objects
        self._lock = threading.Lock()

    def get_vector_docs(self, session_id: str):
        with self._lock:
            return self._vector_docs.get(session_id)

    def set_vector_docs(self, session_id: str, docs: list):
        with self._lock:
            logger.info(f"Caching {len(docs)} documents for session: {session_id}")
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
            self._metadata.pop(session_id, None)

    def clear(self):
        with self._lock:
            self._vector_docs.clear()
            self._metadata.clear()

# Singleton instance
session_cache = SessionCache()


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
            {"embedding": 1, "text": 1, "chapter": 1, "parent_chapter_index": 1, "pov": 1, "_id": 0}
        )
        docs = list(cursor)
        session_cache.set_vector_docs(session_id, docs)
        logger.info(f"Background cache loaded {len(docs)} docs for session {session_id}")
    except Exception as e:
        logger.error(f"Failed to background cache session {session_id}: {e}")