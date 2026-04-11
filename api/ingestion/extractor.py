import os
import json
from google import genai
from google.genai import types
from api.config.settings import app_settings

def extract_metadata(chunk_text: str) -> dict:
    """Extract a summary, chapter title, and character list from text."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")
    
    prompt = f"""
    Given the following text segment, perform three tasks:
    1. Write a 7-10 sentence summary.
    2. Identify the likely chapter name or number. If none is found, return "Unknown".
    3. Make a list of character names mentioned in this segment.
    
    Return the result EXACTLY as a JSON object with the keys "summary", "chapter", and "characters".
    Do not wrap the JSON in Markdown code blocks (e.g. ```json). Just return the raw JSON object.

    Text Segment:
    {chunk_text}
    """

    client = genai.Client(api_key=api_key)
    
    response = client.models.generate_content(
        model=app_settings.get_model(),
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
            response_schema={
                "type": "OBJECT",
                "properties": {
                    "summary": {"type": "STRING"},
                    "chapter": {"type": "STRING"},
                    "characters": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"}
                    }
                },
                "required": ["summary", "chapter", "characters"]
            }
        )
    )
    
    try:
        # Since we asked for JSON response_mime_type, it should be highly reliable
        raw_text = response.text.strip()
        result = json.loads(raw_text)
        return result
    except json.JSONDecodeError:
        print("Failed to decode JSON from Gemini. Falling back.")
        return {
            "summary": "Extraction failed.",
            "chapter": "Unknown",
            "characters": []
        }
