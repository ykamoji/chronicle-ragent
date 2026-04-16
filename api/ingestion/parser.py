import re
import fitz
from typing import List


def clean_chapter_header(text: str) -> str:
    pattern = r"(^.*?\s*)\(Chapter\s+(\d+)\).*"
    return re.sub(pattern, r"Chapter \2, POV : \1", text)

def extract_text_from_pdf(filepath: str) -> str:
    """Extracts all text from a PDF file."""
    doc = fitz.open(filepath)
    full_text = []
    
    for page in doc:
        # Get text grouped by blocks (paragraphs)
        blocks = page.get_text("blocks")
        
        for b in blocks:
            # b[4] is the text content of the block
            block_text = b[4].replace("\n", " ").strip()
            if block_text:
                full_text.append(block_text)
                
    return "\n\n".join(full_text)

def split_units(paragraph: str) -> List[str]:
    return re.split(r'(?<=[\"”?!\.])\s+', paragraph)

WORDS_PER_TOKEN = 1 / 1.3

def token_counter(text: str) -> int:
    return int(len(text.split()) / WORDS_PER_TOKEN)

def chunk_text(text: str, target_tokens: int = 800, overlap_tokens: int = 150) -> List[str]:
    """Splits text into chunks of approximately `target_tokens` size with `overlap_tokens`.
    Uses paragraph breaks and sentence boundaries for cleaner chunks.
    """
    
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

    chunks = []
    current_units = []
    current_token_count = 0

    for paragraph in paragraphs:
        units = split_units(paragraph)

        for unit in units:
            unit_tokens = token_counter(unit)

            # Handle large unit (fallback)
            if unit_tokens > target_tokens:
                words = unit.split()
                # Estimate word targets based on this specific unit's token density
                ratio = len(words) / max(1, unit_tokens)
                target_words = int(target_tokens * ratio)
                overlap_words = int(overlap_tokens * ratio)
                
                i = 0
                while i < len(words):
                    chunk = " ".join(words[i:i + target_words])
                    chunks.append(chunk)
                    
                    if i + target_words >= len(words):
                        break
                    # 2. Fix large unit fallback: Increment by (target - overlap) to bridge gaps
                    i += max(1, target_words - overlap_words)
                continue

            # Normal accumulation
            if current_token_count + unit_tokens <= target_tokens:
                current_units.append(unit)
                current_token_count += unit_tokens
            else:
                if current_units:
                    chunks.append(" ".join(current_units))

                # 3. Sentence-aware overlap: Grab whole sentences counting backwards
                overlap_units = []
                overlap_count = 0
                for u in reversed(current_units):
                    u_toks = token_counter(u)
                    if overlap_count + u_toks <= overlap_tokens:
                        overlap_units.insert(0, u)
                        overlap_count += u_toks
                    else:
                        break
                
                # Start the next chunk with the overlapping sentences + the new unit
                current_units = overlap_units + [unit]
                current_token_count = overlap_count + unit_tokens

    # Catch the final chunk
    if current_units:
        chunks.append(" ".join(current_units))

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
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

        chunk = text[start:end].strip()

        if len(chunk) > 200000:
            chapters.extend(chunk_text(chunk, target_tokens=15000))
        else:
            chapters.append(chunk)

    if not chapters:
        return chunk_text(text, target_tokens=15000)

    chapters = [clean_chapter_header(ch) for ch in chapters]

    return chapters

if __name__ == "__main__":
    text = extract_text_from_pdf("public/book_5_arc_1.pdf")
    chapters = chunk_by_chapter(text)
    print(len(chapters))
    print("\n")
    for ch in chapters:
        print(ch.split("\n\n")[0])
        # print(hashlib.sha256(ch.encode('utf-8')).hexdigest())

    