from typing import List, Dict, Any
from api.db.mongo import mongo
from api.ingestion.embedder import get_embedding

def perform_vector_search(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Performs a vector search against MongoDB Atlas using cosine similarity."""
    collection = mongo.get_vector_collection()
    if collection is None:
        raise ConnectionError("MongoDB is not connected.")

    # Generate embedding for the query
    query_embedding = get_embedding(query)

    # Note: This relies on an Atlas Vector Search index named 'vector_index'
    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_index",
                "path": "embedding",
                "queryVector": query_embedding,
                "numCandidates": limit * 10,
                "limit": limit
            }
        },
        {
            "$project": {
                "embedding": 0,
                "_id": 0,
                "score": { "$meta": "vectorSearchScore" }
            }
        }
    ]

    results = list(collection.aggregate(pipeline))
    return results
