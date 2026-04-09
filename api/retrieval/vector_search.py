import numpy as np
import logging
from heapq import nlargest
from typing import List, Dict, Any
from api.db.mongo import mongo
from api.db.cache import session_cache
from api.ingestion.embedder import get_embedding

logger = logging.getLogger(__name__)

def perform_vector_search(query: str, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Performs a vector search against MongoDB Atlas using cosine similarity."""
    vector_collection = mongo.get_vector_collection()
    if vector_collection is None:
        raise ConnectionError("MongoDB is not connected.")

    # 1. Check Cache first
    docs = session_cache.get_vector_docs(session_id)
    
    if not docs:
        # Fetch from MongoDB if not cached
        docs = list(
            vector_collection.find(
                {"session_id": {"$in": [session_id]}},
                {"embedding": 1, "text": 1, "chapter": 1, "_id": 0}
            )
        )
        if docs:
            session_cache.set_vector_docs(session_id, docs)

    logger.info(f"Using {len(docs)} documents for vector search in session {session_id}")

    if not docs:
        return []

    # 2. Generate embedding for the query
    query_embedding = get_embedding(query)

    # 3. Perform local vector search (NumPy math)
    embeddings = np.array([doc["embedding"] for doc in docs], dtype="float32")
    query_vec = np.array(query_embedding, dtype="float32")

    scores = embeddings @ query_vec

    for doc, score in zip(docs, scores):
        doc["score"] = float(score)

    results = nlargest(limit, docs, key=lambda x: x["score"])

    return results