from api.retrieval.vector_search import perform_vector_search, extract_query_signals
from api.retrieval.keyword_search import perform_keyword_search
from api.retrieval.character_search import perform_character_search
from api.db.mongo import mongo
from api.db.cache import session_cache
import logging

logger = logging.getLogger(__name__)

def tool_vector_search(query: str, session_id: str) -> str:
    """Semantically searches the document text based on meaning."""
    logger.info(f"Running vector search for: {query} (Session: {session_id})")
    try:
        # Extract signals from query
        signals = extract_query_signals(query)
        logger.info(f"Extracted signals: {signals}")
        results = perform_vector_search(query=query, session_id=session_id, limit=10, **signals)
        if not results:
            return "No matching documents found in vector search."
        rendered = []
        for r in results:
            text = r.get('text', 'No text')
            source = r.get('chapter', 'Unknown source')
            rendered.append(f"[Source: {source}]\n{text}")
        return "\n\n".join(rendered)
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        return f"Error executing vector search: {str(e)}"

def tool_keyword_search(query: str, session_id: str) -> str:
    """Searches for exact matches or regex keywords in the documents."""
    logger.info(f"Running keyword search for: {query} (Session: {session_id})")
    try:
        results = perform_keyword_search(query, session_id, limit=3)
        if not results:
            return "No matching documents found in keyword search."
        rendered = []
        for r in results:
            text = r.get('text', 'No text')
            source = r.get('chapter', 'Unknown source')
            rendered.append(f"[Source: {source}]\n{text}")
        return "\n\n".join(rendered)
    except Exception as e:
        logger.error(f"Keyword search failed: {e}")
        return f"Error executing keyword search: {str(e)}"

def tool_character_lookup(name: str, session_id: str) -> str:
    """Looks up documents mentioning a specific character by name."""
    logger.info(f"Running character lookup for: {name} (Session: {session_id})")
    try:
        results = perform_character_search(name, session_id, limit=3)
        if not results:
            return f"No mentions found for character: {name}"
        rendered = []
        for r in results:
            text = r.get('text', 'No text')
            source = r.get('chapter', 'Unknown source')
            rendered.append(f"[Source: {source}]\n{text}")
        return "\n\n".join(rendered)
    except Exception as e:
        logger.error(f"Character lookup failed: {e}")
        return f"Error looking up character: {str(e)}"

def tool_summary(chapter: str, session_id: str) -> str:
    """Retrieves the summary of a specific chapter from session metadata."""
    
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
                return "MongoDB is not connected."
                
            doc = session_coll.find_one({"session_id": session_id}, {"metadata": 1, "_id": 0})
            if not doc or "metadata" not in doc:
                return f"No metadata found for session: {session_id}"
                
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
        
        if not matches:
            return f"No summaries found matching chapter: {chapter}"
            
        rendered = []
        for m in matches:
            summary = m.get('summary', 'No summary')
            source = m.get('chapter', 'Unknown source')
            rendered.append(f"[Source: {source}]\n{summary}")
        return "\n\n".join(rendered)
    except Exception as e:
        logger.error(f"Summary lookup failed: {e}")
        return f"Error retrieving summary: {str(e)}"

# Registry of tools available to the Agent
TOOLS = {
    "vector_search": tool_vector_search,
    "keyword_search": tool_keyword_search,
    "character_lookup": tool_character_lookup,
    "summary": tool_summary,
}
