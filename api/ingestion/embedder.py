import os
import numpy as np
from google import genai
from google.genai import types
from numpy.linalg import norm

def get_embedding(text: str, is_query: bool = False) -> list[float]:
    """Generates an embedding vector using Google's text-embedding-004 model."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")
    
    client = genai.Client(api_key=api_key)

    task_type = "RETRIEVAL_QUERY" if is_query else "RETRIEVAL_DOCUMENT"
    
    response = client.models.embed_content(
        model='gemini-embedding-001',
        contents=text,
        config=types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=1536,
            
        )
    )

    embedding_values_np = np.array(response.embeddings[0].values)
    normed_embedding = embedding_values_np / np.linalg.norm(embedding_values_np)

    return normed_embedding.tolist()
