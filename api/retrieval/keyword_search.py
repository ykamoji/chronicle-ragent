from typing import List, Dict, Any
import re
from api.db.mongo import mongo
from api.db.cache import session_cache

def perform_keyword_search(query: str, session_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Performs a text search using MongoDB regex or session cache."""
    # 1. Check Cache first
    docs = session_cache.get_vector_docs(session_id)
    
    if not docs:
        collection = mongo.get_vector_collection()
        if collection is None:
            raise ConnectionError("MongoDB is not connected.")
            
        docs = list(collection.find(
            {"session_id": session_id},
            {"embedding": 1, "text": 1, "chapter": 1, "characters": 1, "_id": 0}
        ))
        if docs:
            session_cache.set_vector_docs(session_id, docs)

    if not docs:
        return []

    # 2. Filter in-memory
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    results = []
    
    for d in docs:
        # Check all relevant fields
        fields_to_check = [
            d.get("text", ""),
            d.get("summary", ""),
            d.get("chapter", ""),
            " ".join(d.get("characters", []))
        ]
        
        if any(pattern.search(str(f)) for f in fields_to_check):
            # Create a copy without embedding for the result
            res = {k: v for k, v in d.items() if k != "embedding"}
            results.append(res)
            
        if len(results) >= limit:
            break
            
    return results
