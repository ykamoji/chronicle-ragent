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

def build_patterns(words):
    return [re.compile(rf"\b{re.escape(w)}\b") for w in words]

def normalize(x):
    return (x - x.min()) / (x.max() - x.min() + 1e-6)

def compute_pre_scores(docs, keywords:List[str] = [], characters:List[str] = [], chapters:List[str] = []):
    """Compute pre-scores for documents based on query signals"""

    keywords = [k.lower() for k in keywords]
    characters = [c.lower() for c in characters]
    chapters = [c.lower() for c in chapters]
    
    try:
        if keywords:
            kw_patterns = build_patterns(keywords)
            kw_scores = np.array([
                sum(len(p.findall(doc["text"].lower())) for p in kw_patterns)
                for doc in docs
            ], dtype=np.float32)
        else:
            kw_scores = np.zeros(len(docs), dtype=np.float32)

        if characters:
            char_patterns = build_patterns(characters)
            char_scores = np.array([
                sum(len(p.findall(doc["text"].lower())) for p in char_patterns)
                for doc in docs
            ], dtype=np.float32)
        else:
            char_scores = np.zeros(len(docs), dtype=np.float32)

        if chapters:
            chapter_scores = np.array([
                1 if any(c in doc.get("chapter", "").lower() for c in chapters) else 0
                for doc in docs
            ], dtype=np.float32)
        else:
            chapter_scores = np.zeros(len(docs), dtype=np.float32)

        kw_scores = normalize(kw_scores)
        char_scores = normalize(char_scores)

        return kw_scores, char_scores, chapter_scores

    except Exception as e:
        logger.error(f"Error applying filters: {e}")
        return (
            np.zeros(len(docs), dtype=np.float32),
            np.zeros(len(docs), dtype=np.float32),
            np.zeros(len(docs), dtype=np.float32),
        )


def perform_vector_search(query: str, session_id: str, characters: List[str] = [], keywords: List[str] = [], chapters:List[str] = [], limit: int = 7) -> List[Dict[str, Any]]:
    """Performs a vector search against MongoDB Atlas using cosine similarity."""
    vector_collection = mongo.get_vector_collection()
    if vector_collection is None:
        raise ConnectionError("MongoDB is not connected.")

    # 1. Check Cache first
    docs = session_cache.get_vector_docs(session_id)
    embeddings = session_cache.get_vector_embeddings(session_id)
    
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
            docs = session_cache.get_vector_docs(session_id)
            embeddings = session_cache.get_vector_embeddings(session_id)

    if not docs:
        return []

    logger.info(f"Using {len(docs)} documents for vector search in session {session_id}")

    kw_scores, char_scores, chapter_scores = compute_pre_scores(docs, keywords, characters, chapters)

    pre_scores = (
        0.6 * kw_scores +
        0.25 * char_scores +
        0.15 * chapter_scores
    )

    if np.all(pre_scores == 0):
        candidate_idx = np.arange(len(docs))
    else:
        candidate_k = min(300, max(50, int(0.3 * len(docs))))
        candidate_idx = np.argpartition(pre_scores, -candidate_k)[-candidate_k:]

    # 2. Generate embedding for the query
    query_embedding = get_embedding(query, is_query=True)

    # 3. Perform local vector search (NumPy math)
    candidate_embeddings = embeddings[candidate_idx]
    candidate_docs = [docs[i] for i in candidate_idx]

    logger.info(f"Using {len(candidate_docs)} candidate documents for vector search in session {session_id}")
    
    query_vec = np.asarray(query_embedding, dtype=np.float32)

    scores = candidate_embeddings @ query_vec

    vec_scores = (scores - scores.min()) / (scores.max() - scores.min() + 1e-6)

    final_scores = (
        0.75 * vec_scores +
        0.25 * pre_scores[candidate_idx]
    )
    
    top_k_idx = np.argpartition(final_scores, -limit)[-limit:]
    top_k_idx = top_k_idx[np.argsort(final_scores[top_k_idx])[::-1]]

    results = [candidate_docs[i] for i in top_k_idx]

    return results