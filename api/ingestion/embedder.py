import os
from google import genai
from google.genai import types

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
            task_type=task_type
        )
    )
    
    return response.embeddings[0].values
