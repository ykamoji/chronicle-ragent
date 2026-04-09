from api.retrieval.vector_search import perform_vector_search
from api.retrieval.keyword_search import perform_keyword_search
from api.db.mongo import mongo
import logging

logger = logging.getLogger(__name__)

def tool_vector_search(query: str, session_id: str) -> str:
    """Semantically searches the document text based on meaning."""
    logger.info(f"Running vector search for: {query} (Session: {session_id})")
    try:
        results = perform_vector_search(query, session_id, limit=3)
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
        collection = mongo.get_vector_collection()
        if collection is None:
            return "MongoDB is not connected."
            
        results = list(collection.find(
            {
                "session_id": session_id,
                "characters": {"$regex": name, "$options": "i"}
            },
            {"text": 1, "chapter": 1, "_id": 0}
        ).limit(3))
        
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
    """Retrieves the summary of a specific chapter."""
    logger.info(f"Running summary lookup for chapter: {chapter} (Session: {session_id})")
    try:
        collection = mongo.get_vector_collection()
        if collection is None:
            return "MongoDB is not connected."
            
        results = list(collection.find(
            {
                "session_id": session_id,
                "chapter": {"$regex": chapter, "$options": "i"}
            },
            {"summary": 1, "chapter": 1, "_id": 0}
        ).limit(5))
        
        if not results:
            return f"No summaries found for chapter: {chapter}"
            
        rendered = []
        for r in results:
            summary = r.get('summary', 'No summary')
            source = r.get('chapter', 'Unknown source')
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
