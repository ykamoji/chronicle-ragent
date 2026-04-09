from typing import List, Dict, Any
import re
from api.db.mongo import mongo

def perform_keyword_search(query: str, session_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Performs a text search using MongoDB regex."""
    collection = mongo.get_vector_collection()
    if collection is None:
        raise ConnectionError("MongoDB is not connected.")

    # Convert query into a case-insensitive regex pattern
    pattern = re.compile(query, re.IGNORECASE)

    # Searching across text, summary, chapter, characters fields
    filter_query = {
        "session_id": session_id,
        "$or": [
            {"text": {"$regex": pattern}},
            {"summary": {"$regex": pattern}},
            {"chapter": {"$regex": pattern}},
            {"characters": {"$regex": pattern}}
        ]
    }

    results = list(collection.find(filter_query, {"embedding": 0, "_id": 0}).limit(limit))
    return results
