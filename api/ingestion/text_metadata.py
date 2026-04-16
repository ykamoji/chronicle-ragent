import re
import math
from typing import Any, Dict, List

WORD_RE = re.compile(r"\b[\w']+\b", re.UNICODE)


def extract_rag_stats( chapters: List[str], chunk_tokens: int = 800, words_per_token: float = 1 / 1.3, overlap_tokens: int = 150) -> Dict[str, Any]:
    if not isinstance(chapters, list):
        raise TypeError("chapters must be a list of strings")

    stride_tokens = chunk_tokens - overlap_tokens
    if stride_tokens <= 0:
        raise ValueError("overlap_tokens must be less than chunk_tokens")

    total_words = 0
    global_vocab = set()
    estimated_total_chunks = 0

    for chapter in chapters:
        if not isinstance(chapter, str):
            raise TypeError("all chapters must be strings")

        cleaned = chapter.strip()
        if not cleaned:
            continue

        words = WORD_RE.findall(cleaned.lower())
        word_count = len(words)

        if word_count == 0:
            continue

        token_estimate = word_count / words_per_token

        # overlap-aware chunking
        if token_estimate <= chunk_tokens:
            chunk_estimate = 1
        else:
            chunk_estimate = math.ceil(
                (token_estimate - overlap_tokens) / stride_tokens
            )

        estimated_total_chunks += chunk_estimate
        total_words += word_count
        global_vocab.update(words)

    chapter_count = len(chapters)
    estimated_total_tokens = total_words / words_per_token if total_words else 0.0

    # utilization
    total_capacity_tokens = estimated_total_chunks * chunk_tokens
    chunk_utilization_pct = (
        (estimated_total_tokens / total_capacity_tokens) * 100
        if total_capacity_tokens
        else 0.0
    )

    # redundancy
    overlap_redundancy_pct = (
        ((total_capacity_tokens - estimated_total_tokens) / estimated_total_tokens) * 100
        if estimated_total_tokens
        else 0.0
    )

    lexical_density = (
        len(global_vocab) / total_words if total_words else 0.0
    )

    return {
        "general": {
            "total_chapters": chapter_count,
            "total_words": total_words,
        },
        "chunks": {
            "total_tokens": round(estimated_total_tokens, 2),
            "total_chunks": estimated_total_chunks,
            "chunk_tokens": chunk_tokens,
            "overlap_tokens": overlap_tokens,
            "chunk_utilization_pct": round(chunk_utilization_pct, 2),
            "overlap_redundancy_pct": round(overlap_redundancy_pct, 2),
        },
        "quality": {
            "lexical_density": round(lexical_density, 4),
            "unique_words": len(global_vocab),
        },
    }