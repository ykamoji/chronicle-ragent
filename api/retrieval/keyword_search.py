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
            {"embedding": 1, "text": 1, "chapter": 1, "_id": 0}
        ))
        if docs:
            session_cache.set_vector_docs(session_id, docs)

    if not docs:
        return []

    # 2. Get metadata to fetch summary
    session_metadata = session_cache.get_metadata(session_id)
    if session_metadata is None:
        session_coll = mongo.get_sessions_collection()
        if session_coll is not None:
            doc = session_coll.find_one({"session_id": session_id}, {"metadata": 1, "_id": 0})
            if doc and "metadata" in doc:
                session_metadata = doc.get("metadata", [])
                session_cache.set_metadata(session_id, session_metadata)
    
    if not session_metadata:
        session_metadata = []

    # Create map from chapter to meta
    chapter_meta = {m.get("chapter", ""): m for m in session_metadata}

    # 3. Filter in-memory
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    results = []
    
    for d in docs:
        chapter = d.get("chapter", "")
        meta = chapter_meta.get(chapter, {})
        
        # Check all relevant fields
        fields_to_check = [
            d.get("text", ""),
            meta.get("summary", ""),
            chapter
        ]
        
        if any(pattern.search(str(f)) for f in fields_to_check):
            results.append(d)
            
        if len(results) >= limit:
            break
            
    return results
