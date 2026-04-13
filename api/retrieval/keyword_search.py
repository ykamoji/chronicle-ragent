from typing import List, Dict, Any
import re
from rank_bm25 import BM25Okapi
from api.db.mongo import mongo
from api.db.cache import session_cache

def tokenize(text: str) -> List[str]:
    """Standard tokenizer for BM25: lowercase and split into words."""
    return re.findall(r'\w+', text.lower())

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

    # 3. BM25 Logic
    # OPTIMIZATION: Combine text/meta and tokenize
    corpus_tokens = []
    for d in docs:
        meta = chapter_meta.get(d.get("chapter", ""), {})
        # Create a "Searchable Document" by combining fields
        rich_text = f"{d.get('text', '')} {meta.get('summary', '')} {d.get('chapter', '')}"
        corpus_tokens.append(tokenize(rich_text))

    # Initialize BM25 with the tokenized corpus
    bm25 = BM25Okapi(corpus_tokens)
    
    # Tokenize the user query (e.g., "Heraknus feared strength")
    tokenized_query = tokenize(query)
    
    # Get scores for all documents
    doc_scores = bm25.get_scores(tokenized_query)

    # 4. Filter and Rank
    results = []
    for i, doc in enumerate(docs):
        score = doc_scores[i]
        if score > 0:  # Only include if there's at least one term match
            # We create a copy to avoid mutating the cached object
            result_doc = doc.copy()
            result_doc["bm25_score"] = score
            results.append(result_doc)

    # Sort by score descending
    results.sort(key=lambda x: x["bm25_score"], reverse=True)
            
    return results[:limit]
