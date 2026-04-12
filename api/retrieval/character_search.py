from typing import Dict, List, Any
from api.db.mongo import mongo
from api.db.cache import session_cache

def perform_character_search(name: str, session_id: str) -> List[Dict[str, Any]]:
    """Performs a character search using MongoDB or session cache."""
    # 1. Get metadata to find matching chapters and their summaries
    session_metadata = session_cache.get_metadata(session_id)
    if session_metadata is None:
        session_coll = mongo.get_sessions_collection()
        if session_coll is not None:
            doc = session_coll.find_one({"session_id": session_id}, {"metadata": 1, "_id": 0})
            if doc and "metadata" in doc:
                session_metadata = doc.get("metadata", [])
                session_cache.set_metadata(session_id, session_metadata)
    
    if not session_metadata:
        return []

    name_lower = name.lower()
    results = []
    
    for meta in session_metadata:
        chars = meta.get("characters", [])
        if any(name_lower in char.lower() for char in chars):
            results.append({
                "text": meta.get("summary", ""),
                "chapter": meta.get("chapter", "")
            })

    return results