import re
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

    results = []
    # 2. Parse the query string into a list of individual names
    # Splits on commas OR spaces, then filters out empty strings
    search_terms = [t.lower() for t in re.split(r'[,\s]+', name) if t.strip()]

    if not search_terms:
        return []
    
    # 3. Filter metadata for matches
    for meta in session_metadata:
        # Get characters in this chapter and lowercase them
        chars_in_chapter = [c.lower() for c in meta.get("characters", [])]
        
        # Logic: If any search term is part of any character name in the chapter
        match_found = any(
            any(term in char for char in chars_in_chapter)
            for term in search_terms
        )

        if match_found:
            results.append({
                "text": meta.get("summary", ""),
                "chapter": meta.get("chapter", "")
            })

    return results