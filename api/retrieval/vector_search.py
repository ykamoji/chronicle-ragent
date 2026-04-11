import numpy as np
import re
import logging
import os
import json
from google import genai
from google.genai import types
from typing import List, Dict, Any
from api.db.mongo import mongo
from api.db.cache import session_cache
from api.ingestion.embedder import get_embedding
from api.config.settings import app_settings

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """
You are a search query analyzer.
Your task is to extract structured signals that will be used to retrieve relevant text chunks.

Return ONLY valid JSON in this format:
{
  "characters": [],
  "keywords": [],
  "chapters": []
}

Rules:
- characters = character names explicitly mentioned in the query
- keywords = 2 to 5 important terms that help retrieve relevant passages
- chapters = chapter names or numbers explicitly mentioned in the query
- Do NOT hallucinate or infer new terms
- Do NOT include generic words (what, did, when, etc.)
- Keep keywords short (1-2 words max)
- Only include words present in the query

Goal:
- Maximize retrieval relevance
- Minimize noise

Query:
"""

def extract_query_signals(query: str) -> dict:

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=app_settings.get_model(),
        contents=f"{EXTRACTION_PROMPT}{query}",
        config=types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=150,
            response_mime_type="application/json",
            response_schema={
                "type": "OBJECT",
                "properties": {
                    "characters": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"}
                    },
                    "keywords": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"}
                    },
                    "chapters": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"}
                    }
                },
                "required": ["characters", "keywords", "chapters"]
            }
        )
    )

    try:
        result = safe_json_extract(response.text.strip())
        return result
    except Exception as e:
        logger.warning(f"Failed to parse query signals: {e}")
        return {"characters": [], "keywords": [], "chapters":[]}

def safe_json_extract(text: str) -> dict:
    try:
        # Extract first JSON object using regex
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError("No JSON object found")

        json_str = match.group(0)
        return json.loads(json_str)

    except Exception as e:
        logger.warning(f"JSON extraction failed: {e}")
        return {"characters": [], "keywords": [], "chapters": []}

def _apply_filters(docs, characters:List[str] = [], keywords:List[str] = [], chapters:List[str] = []):
    """Filter documents in-memory"""
    
    filtered = docs

    characters = [c.lower() for c in (characters or [])]
    keywords = [k.lower() for k in (keywords or [])]
    chapters = [c.lower() for c in (chapters or [])]

    try:
        if characters:
            c_filtered = [
                d for d in filtered
                if any(c in [dc.lower() for dc in d.get("characters", [])] for c in characters)
            ]
            if c_filtered:
                filtered = c_filtered

        if keywords:
            k_filtered = [
                    d for d in filtered
                    if any(k in d.get("text", "").lower() for k in keywords)
                ]

            # Apply only if not too restrictive
            if len(k_filtered) >= max(3, int(0.2 * len(filtered))):
                filtered = k_filtered
        
        if chapters:
            ch_filtered = [
                d for d in filtered
                if any(c in d.get("chapter", "").lower() for c in chapters)
            ]

            if ch_filtered:
                filtered = ch_filtered

    except Exception as e:
        logger.error(f"Error applying filters: {e}")
        
    return filtered


def perform_vector_search(query: str, session_id: str, characters: List[str] = [], keywords: List[str] = [], chapters:List[str] = [], limit: int = 10) -> List[Dict[str, Any]]:
    """Performs a vector search against MongoDB Atlas using cosine similarity."""
    vector_collection = mongo.get_vector_collection()
    if vector_collection is None:
        raise ConnectionError("MongoDB is not connected.")

    # 1. Check Cache first
    docs = session_cache.get_vector_docs(session_id)
    
    if not docs:
        # Fetch from MongoDB if not cached
        docs = list(
            vector_collection.find(
                {"session_id": {"$in": [session_id]}},
                {"embedding": 1, "text": 1, "chapter": 1, "characters": 1, "_id": 0}
            )
        )
        if docs:
            session_cache.set_vector_docs(session_id, docs)

    if not docs:
        return []

    logger.info(f"Using {len(docs)} documents for vector search in session {session_id}")

    filtered_docs = _apply_filters(docs, characters, keywords, chapters)

    logger.info(f"Using {len(filtered_docs)} filtered documents for vector search in session {session_id}")

    # 2. Generate embedding for the query
    query_embedding = get_embedding(query, is_query=True)

    # 3. Perform local vector search (NumPy math)
    embeddings = np.ascontiguousarray([doc["embedding"] for doc in filtered_docs], dtype=np.float32)
    
    query_vec = np.asarray(query_embedding, dtype=np.float32)

    scores = embeddings @ query_vec
    
    top_k_idx = np.argpartition(scores, -limit)[-limit:]
    top_k_idx = top_k_idx[np.argsort(scores[top_k_idx])[::-1]]

    results = [
        {**filtered_docs[i], "score": float(scores[i])}
        for i in top_k_idx
    ]

    return results