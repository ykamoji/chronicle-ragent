import json
from google import genai
from google.genai import types
from api.config import settings

def extract_metadata(chunk_text: str) -> dict:
    """Uses Google Gemini to extract a summary, chapter title, and character list from text."""
    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY is not set.")
    
    prompt = f"""
    Given the following text segment, perform three tasks:
    1. Write a 1-2 sentence summary.
    2. Identify the likely chapter name or number. If none is found, return "Unknown".
    3. Make a list of character names mentioned in this segment.
    
    Return the result EXACTLY as a JSON object with the keys "summary", "chapter", and "characters".
    Do not wrap the JSON in Markdown code blocks (e.g. ```json). Just return the raw JSON object.

    Text Segment:
    {chunk_text}
    """

    client = genai.Client(api_key=settings.gemini_api_key)
    
    # gemini-2.0-flash is current recommended small model
    response = client.models.generate_content(
        model='gemini-2.0-flash',
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
