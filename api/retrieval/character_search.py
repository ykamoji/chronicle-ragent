from typing import Dict, List, Any
from api.db.mongo import mongo
from api.db.cache import session_cache

def perform_character_search(name: str, session_id: str) -> List[Dict[str, Any]]:
    """Performs a character search using MongoDB or session cache."""
    # 1. Check Cache first
    docs = session_cache.get_vector_docs(session_id)
    
    if not docs:
        # Fetch from MongoDB if not cached
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

    name_lower = name.lower()
    results = [
        {"text": d["text"], "chapter": d["chapter"]}
        for d in docs
        if any(name_lower in char.lower() for char in d.get("characters", []))
    ]
        
    return results