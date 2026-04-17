import logging
from typing import List, Dict, Any
from api.db.mongo import mongo
from api.ingestion.embedder import get_embedding

logger = logging.getLogger(__name__)

def compute_rrf(rankings, k=60):
    scores = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank + 1)
    return scores        


def perform_vector_search(query: str, session_id: str, limit: int = 7) -> List[Dict[str, Any]]:
    """Performs a vector search against MongoDB Atlas using cosine similarity."""
    vector_collection = mongo.get_vector_collection()
    if vector_collection is None:
        raise ConnectionError("MongoDB is not connected.")

    collection = mongo.get_vector_collection()

    query_embedding = get_embedding(query, is_query=True)

    # ---------------------------
    # 1. BM25 (Atlas Search)
    # ---------------------------
    bm25_pipeline = [
        {
            "$search": {
                "index": "search_index",
                "compound": {
                    "must": [
                        {
                            "text": {
                                "query": query,
                                "path": "text"
                            }
                        }
                    ],
                    "filter": [
                        {
                            "equals": {
                                "path": "session_id",
                                "value": session_id
                            }
                        }
                    ]
                }
            }
        },
        {"$limit": 50},
        {
            "$project": {
                "_id": 1,
                "text": 1,
                "chapter": 1,
            }
        }
    ]

    bm25_docs = list(collection.aggregate(bm25_pipeline))

    # ---------------------------
    # 2. Vector Search
    # ---------------------------
    vector_pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_index",
                "path": "embedding",
                "queryVector": query_embedding,
                "numCandidates": 500,
                "limit": 100,
                "filter": {
                    "session_id": session_id
                }
            }
        },
        {
            "$project": {
                "_id": 1,
                "text": 1,
                "chapter": 1
            }
        }
    ]

    vector_docs = list(collection.aggregate(vector_pipeline))

    if not bm25_docs and not vector_docs:
        return []

    # ---------------------------
    # 3. Rankings
    # ---------------------------
    bm25_ids = [str(doc["_id"]) for doc in bm25_docs]
    vector_ids = [str(doc["_id"]) for doc in vector_docs]

    # ---------------------------
    # 4. RRF Fusion
    # ---------------------------
    rrf_scores = compute_rrf([bm25_ids, vector_ids])

    # ---------------------------
    # 5. Merge docs
    # ---------------------------
    doc_map = {}
    for doc in bm25_docs + vector_docs:
        doc_id = str(doc["_id"])
        if doc_id not in doc_map:
            doc_map[doc_id] = doc

    # ---------------------------
    # 6. Final ranking
    # ---------------------------
    ranked = sorted(
        doc_map.items(),
        key=lambda x: rrf_scores.get(x[0], 0),
        reverse=True
    )

    return [doc for _, doc in ranked[:limit]]