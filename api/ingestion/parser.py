import os
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

def chunk_text(text: str, target_tokens: int = 400) -> List[str]:
    """Splits text into chunks of approximately `target_tokens` size.
    Uses paragraph breaks where possible for cleaner chunks.
    """
    target_chars = target_tokens * CHARS_PER_TOKEN
    paragraphs = text.split('\n\n')
    
    chunks = []
    current_chunk = ""
    
    for paragraph in paragraphs:
        if len(current_chunk) + len(paragraph) < target_chars:
            current_chunk += paragraph + "\n\n"
        else:
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            current_chunk = paragraph + "\n\n"
            
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
        
    # Handle massive single paragraphs
    final_chunks = []
    for chunk in chunks:
        if len(chunk) > target_chars * 1.5:
            # Overly large chunk, force split by words
            words = chunk.split()
            temp_chunk = []
            temp_len = 0
            for word in words:
                if temp_len + len(word) + 1 > target_chars:
                    final_chunks.append(" ".join(temp_chunk))
                    temp_chunk = [word]
                    temp_len = len(word)
                else:
                    temp_chunk.append(word)
                    temp_len += len(word) + 1
            if temp_chunk:
                final_chunks.append(" ".join(temp_chunk))
        else:
            final_chunks.append(chunk)
            
    return final_chunks
