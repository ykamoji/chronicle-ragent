import os
from google import genai
from google.genai import types

def get_embedding(text: str) -> list[float]:
    """Generates an embedding vector using Google's text-embedding-004 model."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")
    
    client = genai.Client(api_key=api_key)
    
    response = client.models.embed_content(
        model='gemini-embedding-001',
        contents=text,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT"
        )
    )
    
    return response.embeddings[0].values
