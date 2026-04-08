import os
import re
import fitz  # PyMuPDF
from typing import List

# Simple token estimation: 1 token is approx 4 characters
CHARS_PER_TOKEN = 4

def extract_text_from_pdf(filepath: str) -> str:
    """Extracts all text from a PDF file."""
    doc = fitz.open(filepath)
    text = ""
    for page in doc:
        text += page.get_text() + "\n"
    return text

def chunk_text(text: str, target_tokens: int = 400, overlap_tokens: int = 75) -> List[str]:
    """Splits text into chunks of approximately `target_tokens` size with `overlap_tokens`.
    Uses paragraph breaks where possible for cleaner chunks.
    """
    CHARS_PER_TOKEN = 4
    target_chars = target_tokens * CHARS_PER_TOKEN
    overlap_chars = overlap_tokens * CHARS_PER_TOKEN

    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

    chunks = []
    current_chunk = ""

    for paragraph in paragraphs:
        # If paragraph itself is too big → split early
        if len(paragraph) > target_chars:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""

            words = paragraph.split()
            temp = ""
            for word in words:
                if len(temp) + len(word) + 1 > target_chars:
                    chunks.append(temp.strip())
                    temp = word + " "
                else:
                    temp += word + " "
            if temp:
                chunks.append(temp.strip())
            continue

        # Normal accumulation
        if len(current_chunk) + len(paragraph) + 2 <= target_chars:
            current_chunk += paragraph + "\n\n"
        else:
            chunks.append(current_chunk.strip())

            # Overlap
            overlap_text = current_chunk[-overlap_chars:]
            current_chunk = overlap_text + paragraph + "\n\n"

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks

def chunk_by_chapter(text: str) -> List[str]:
    """Splits text into chapters based on standard 'Chapter' prefixes.
    Falls back to large chunks if chapters are too big or undetected.
    """
    pattern = r"(?im)^[^\n]*\(\s*Chapter\s+\d+[^\n]*\)"
    matches = list(re.finditer(pattern, text))

    chapters = []

    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i+1].start() if i+1 < len(matches) else len(text)

        chunk = text[start:end].strip()

        if len(chunk) > 200000:
            chapters.extend(chunk_text(chunk, target_tokens=15000))
        else:
            chapters.append(chunk)

    if not chapters:
        return chunk_text(text, target_tokens=15000)

    return chapters
