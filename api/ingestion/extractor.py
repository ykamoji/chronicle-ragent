import os
import json
import re
from google import genai
from google.genai import types
from api.config.settings import app_settings

def extract_metadata(chunk_text: str) -> dict:
    """Extract a summary, chapter title, and character list from text."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")
    
    prompt = f"""
    You are given a full book chapter.

    Your task is to extract structured metadata from it.

    Tasks:
    1. Write a detailed plot summary that captures all major events across the entire chapter.
    2. Identify the chapter name or number ONLY if it is explicitly present in the text. Otherwise return "Unknown".
    3. Extract ALL explicitly mentioned character names.

    SUMMARY REQUIREMENTS:
    - The summary MUST be between 12 and 20 sentences.
    - It must cover the full progression of the chapter (beginning → middle → end).
    - Do not overly compress—include key events, conflicts, and transitions.
    - Do not add information not present in the text.
    
    CHARACTER EXTRACTION RULES:
    - Include ONLY explicitly mentioned proper names.
    - Exclude roles or descriptions (e.g., "the man", "her mother", "the guard").
    - Include both major and minor characters.
    - Pay special attention to names that appear only once.
    - Deduplicate names (each name appears only once).
    - Preserve original casing.

    GENERAL RULES:
    - Do NOT hallucinate or infer missing details.
    - Do NOT include explanations or extra text.
    - Output MUST be valid JSON only.
    - Use EXACTLY these keys: "summary", "chapter", "characters".

    Chapter:
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
        if hasattr(response, "parsed") and response.parsed:
            return response.parsed
        
        result = safe_json_extract(response.text)
        return result
    except Exception as e:
        print(f"Failed to extract metadata {e}")
        return {
            "summary": "",
            "chapter": "Unknown",
            "characters": []
        }

def safe_json_extract(text: str) -> dict:
    try:
        # Extract first JSON object using regex
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError("No JSON object found")

        json_str = match.group(0)
        return json.loads(json_str)

    except Exception as e:
        return {"characters": [], "summary": "", "chapter": "Unknown"}
