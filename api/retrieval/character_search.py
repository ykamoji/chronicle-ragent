from typing import Dict, List, Any
from api.db.mongo import mongo

def perform_character_search(name: str, session_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Performs a character search using MongoDB regex."""
    collection = mongo.get_vector_collection()
    if collection is None:
        return ConnectionError("MongoDB is not connected.")

    results = list(collection.find({
                "session_id": session_id,
                "characters": {"$regex": name, "$options": "i"}
            },
            {"text": 1, "chapter": 1, "_id": 0}
        ))
        
    return results