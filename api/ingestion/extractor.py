import os
import json
import re
import logging
from google import genai
from google.genai import types
from api.config.settings import app_settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are a highly precise metadata extraction system. 
Your task is to read a provided book chapter and output strictly valid JSON.

Tasks:
1. Write a detailed plot summary that captures all major events across the entire chapter. Include key events and transitions.
2. Identify the chapter name or number ONLY if it is explicitly present in the text. Otherwise return "Unknown".
3. Extract ALL explicitly mentioned character names.
4. Extract the POV of the chapter, the name of the character whose perspective is being followed. If no POV found, return "Unknown".

SUMMARY REQUIREMENTS:
- The summary MUST be between 12 and 20 sentences.
- Include key events, conflicts, and transitions.
- Do not add information not present in the text.
    
CHARACTER EXTRACTION RULES:
- Include ONLY explicitly mentioned proper names.
- Exclude roles or descriptions (e.g., "the man", "her mother", "the guard").
- Pay special attention to names that appear only once.
- Deduplicate names (each name appears only once).
- Preserve original casing.

GENERAL RULES:
- Use your reasoning process to draft the summary and count the sentences to ensure it meets the 12-20 sentence constraint before outputting the final JSON.
- Use your reasoning process to compile a rough list of characters, filter out roles/descriptions, and deduplicate the list before finalizing the JSON array.
- Do NOT hallucinate or infer missing details.
- Do NOT include markdown blocks (like ```json).
- Use EXACTLY these keys: "summary" (string), "POV" (string), "chapter" (string), "characters" (array of strings).

Example Output:
{
  "summary": "Sarah finds herself in a...",
  "chapter": "Chapter 4",
  "POV": "Sarah",
  "characters": ["Sarah", "Marcus", "Elara"]
}
"""

def extract_metadata(chunk_text: str) -> dict:
    """Extract a summary, chapter title, and character list from text."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")
    
    USER_PROMPT = f"""
    Extract the metadata from the following chapter:

    <chapter_text>
    {chunk_text}
    </chapter_text>
    """

    client = genai.Client(api_key=api_key)
    
    try:
        response = client.models.generate_content(
            model=app_settings.get_model(),
            contents=SYSTEM_PROMPT +"\n"+ USER_PROMPT,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "summary": {"type": "STRING"},
                        "chapter": {"type": "STRING"},
                        "POV": {"type": "STRING"},
                        "characters": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"}
                        }
                    },
                    "required": ["summary", "chapter", "POV", "characters"]
                },
                thinking_config=types.ThinkingConfig(
                    thinking_level="HIGH"
                )
            )
        )

        # Since we asked for JSON response_mime_type, it should be highly reliable
        if hasattr(response, "parsed") and response.parsed:
            return response.parsed, True
        
        result = safe_json_extract(response.text)
        return result, True
    except Exception as e:
        logger.error(f"Failed to extract metadata {e}")
        return {
            "summary": "",
            "chapter": "Unknown",
            "POV": "Unknown",
            "characters": []
        }, False

def safe_json_extract(text: str) -> dict:
    try:
        # Extract first JSON object using regex
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError("No JSON object found")

        json_str = match.group(0)
        return json.loads(json_str)

    except Exception as e:
        return {"characters": [], "summary": "",  "POV": "Unknown", "chapter": "Unknown"}
