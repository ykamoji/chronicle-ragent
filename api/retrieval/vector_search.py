import numpy as np
import logging
from heapq import nlargest
from typing import List, Dict, Any
from api.db.mongo import mongo
from api.ingestion.embedder import get_embedding

logger = logging.getLogger(__name__)

def perform_vector_search(query: str, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Performs a vector search against MongoDB Atlas using cosine similarity."""
    vector_collection = mongo.get_vector_collection()
    if vector_collection is None:
        raise ConnectionError("MongoDB is not connected.")

    # Generate embedding for the query
    query_embedding = get_embedding(query)

    # # Note: This relies on an Atlas Vector Search index named 'vector_index'
    # pipeline = [
    #     {
    #         "$vectorSearch": {
    #             "index": "vector_index",
    #             "path": "embedding",
    #             "queryVector": query_embedding,
    #             "numCandidates": limit * 10,
    #             "limit": limit,
    #             "filter": { "session_id": { "$in": [session_id] } }
    #         }
    #     },
    #     {
    #         "$project": {
    #             "embedding": 0,
    #             "_id": 0,
    #             "score": { "$meta": "vectorSearchScore" }
    #         }
    #     }
    # ]

    # results = list(vector_collection.aggregate(pipeline))

    docs = list(
        vector_collection.find(
            {"session_id": {"$in": [session_id]}},
            {"embedding": 1, "text": 1, "chapter":1 ,"_id": 0}
        )
    )

    logger.info(f"Found {len(docs)} documents for session {session_id}")

    if not docs:
        return []

    embeddings = np.array([doc["embedding"] for doc in docs], dtype="float32")
    query_vec = np.array(query_embedding, dtype="float32")

    scores = embeddings @ query_vec

    for doc, score in zip(docs, scores):
        doc["score"] = float(score)

    results = nlargest(limit, docs, key=lambda x: x["score"])

    return results