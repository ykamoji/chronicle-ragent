from api.retrieval.vector_search import perform_vector_search
from api.retrieval.keyword_search import perform_keyword_search
from api.retrieval.character_search import perform_character_search
from api.db.mongo import mongo
from api.db.cache import session_cache
import logging

logger = logging.getLogger(__name__)

def tool_vector_search(query: str, session_id: str) -> tuple[str, dict]:
    """
    Semantically searches the story text using vector embeddings. 
    Best for finding themes, moods, or general plot points.
    """
    
    import time
    start_time = time.time()
    logger.info(f"Running vector search for: {query} (Session: {session_id})")
    try:
        results = perform_vector_search(query, session_id, limit=7)
        time_taken = time.time() - start_time
        metrics = {"tool_name": "vector_search", "time_taken": round(time_taken, 3), "docs_retrieved": len(results) if results else 0, "model_name": "gemini-embedding-001"}
        
        if not results:
            return "No matching documents found in vector search.", metrics
        rendered = []
        for r in results:
            text = r.get('text', 'No text')
            source = r.get('chapter', 'Unknown source')
            rendered.append(f"[Source: {source}]\n{text}")
        return "\n\n".join(rendered), metrics
    except Exception as e:
        time_taken = time.time() - start_time
        metrics = {"tool_name": "vector_search", "time_taken": round(time_taken, 3), "docs_retrieved": 0, "model_name": "gemini-embedding-001", "error": str(e)}
        logger.error(f"Vector search failed: {e}")
        return f"Error executing vector search: {str(e)}", metrics

def tool_keyword_search(query: str, session_id: str) -> tuple[str, dict]:
    """
    Searches for exact matches or regex keywords. 
    Use this for rare words, specific item names, or exact phrases.
    """

    import time
    start_time = time.time()
    logger.info(f"Running keyword search for: {query} (Session: {session_id})")
    try:
        results = perform_keyword_search(query, session_id, limit=5)
        time_taken = time.time() - start_time
        metrics = {"tool_name": "keyword_search", "time_taken": round(time_taken, 3), "docs_retrieved": len(results) if results else 0}
        
        if not results:
            return "No matching documents found in keyword search.", metrics
        rendered = []
        for r in results:
            text = r.get('text', 'No text')
            source = r.get('chapter', 'Unknown source')
            rendered.append(f"[Source: {source}]\n{text}")
        return "\n\n".join(rendered), metrics
    except Exception as e:
        time_taken = time.time() - start_time
        metrics = {"tool_name": "keyword_search", "time_taken": round(time_taken, 3), "docs_retrieved": 0, "error": str(e)}
        logger.error(f"Keyword search failed: {e}")
        return f"Error executing keyword search: {str(e)}", metrics

def tool_character_lookup(name: str, session_id: str) -> tuple[str, dict]:
    """
    Looks up all documents and mentions related to a specific character by name.
    """

    import time
    start_time = time.time()
    logger.info(f"Running character lookup for: {name} (Session: {session_id})")
    try:
        results = perform_character_search(name, session_id)
        time_taken = time.time() - start_time
        metrics = {"tool_name": "character_lookup", "time_taken": round(time_taken, 3), "docs_retrieved": len(results) if results else 0}
        
        if not results:
            return f"No mentions found for character: {name}", metrics
        rendered = []
        for r in results:
            text = r.get('text', 'No text')
            source = r.get('chapter', 'Unknown source')
            rendered.append(f"[Source: {source}]\n{text}")
        return "\n\n".join(rendered), metrics
    except Exception as e:
        time_taken = time.time() - start_time
        metrics = {"tool_name": "character_lookup", "time_taken": round(time_taken, 3), "docs_retrieved": 0, "error": str(e)}
        logger.error(f"Character lookup failed: {e}")
        return f"Error looking up character: {str(e)}", metrics

def tool_summary(chapter: str, session_id: str) -> tuple[str, dict]:
    """
    Retrieves chapter summaries. 
    If a chapter number is provided, returns that specific summary. 
    If no chapter is provided, returns summaries for the entire book.
    """

    import time
    start_time = time.time()
    
    if chapter == "":
        chapter = "all"

    logger.info(f"Running summary lookup for chapter: {chapter} (Session: {session_id})")
    try:
        # 1. Check Cache first
        metadata = session_cache.get_metadata(session_id)
        
        if metadata is None:
            # Fetch from MongoDB if not cached
            session_coll = mongo.get_sessions_collection()
            if session_coll is None:
                time_taken = time.time() - start_time
                metrics = {"tool_name": "summary", "time_taken": round(time_taken, 3), "docs_retrieved": 0, "error": "DB not connected"}
                return "MongoDB is not connected.", metrics
                
            doc = session_coll.find_one({"session_id": session_id}, {"metadata": 1, "_id": 0})
            if not doc or "metadata" not in doc:
                time_taken = time.time() - start_time
                metrics = {"tool_name": "summary", "time_taken": round(time_taken, 3), "docs_retrieved": 0, "error": "Metadata not found"}
                return f"No metadata found for session: {session_id}", metrics
                
            metadata = doc.get("metadata", [])
            session_cache.set_metadata(session_id, metadata)
        
        if chapter == "all":
            matches = metadata
        else:
            import re
            # Filter metadata for matching chapter name (case-insensitive)
            matches = [
                m for m in metadata 
                if re.search(re.escape(chapter), m.get("chapter", ""), re.IGNORECASE)
            ]
        
        time_taken = time.time() - start_time
        metrics = {"tool_name": "summary", "time_taken": round(time_taken, 3), "docs_retrieved": len(matches) if matches else 0}

        if not matches:
            return f"No summaries found matching chapter: {chapter}", metrics
            
        rendered = []
        for m in matches:
            summary = m.get('summary', 'No summary')
            source = m.get('chapter', 'Unknown source')
            rendered.append(f"[Source: {source}]\n{summary}")
        return "\n\n".join(rendered), metrics
    except Exception as e:
        time_taken = time.time() - start_time
        metrics = {"tool_name": "summary", "time_taken": round(time_taken, 3), "docs_retrieved": 0, "error": str(e)}
        logger.error(f"Summary lookup failed: {e}")
        return f"Error retrieving summary: {str(e)}", metrics

# Registry of tools available to the Agent
TOOLS = {
    "vector_search": tool_vector_search,
    "keyword_search": tool_keyword_search,
    "character_lookup": tool_character_lookup,
    "summary": tool_summary,
}

TOOLS_NAME_MAP = {
    "vector_search": "Vector",
    "keyword_search": "Keyword",
    "character_lookup": "Character",
    "summary": "Summary",
}