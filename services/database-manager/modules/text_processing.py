import os
import re
from pypdf import PdfReader


def allowed_file(filename, allowed_extensions):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


def chunk_text(text, chunk_size=500, overlap=100):
    """Split text into overlapping chunks."""
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start += chunk_size - overlap

    return chunks


def sanitize_text(text):
    """Sanitize text to avoid DB unicode/control character issues."""
    if not text:
        return ''

    sanitized = text.replace('\x00', '')
    sanitized = re.sub(r'[\x01-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', ' ', sanitized)
    sanitized = re.sub(r'\r\n?', '\n', sanitized)
    sanitized = re.sub(r'[ \t]+', ' ', sanitized)
    sanitized = re.sub(r'\n{3,}', '\n\n', sanitized)
    return sanitized.strip()


def extract_text_from_file(filepath):
    """Extract text from uploaded file."""
    try:
        print(f"[DEBUG] Extracting text from: {filepath}")
        print(f"[DEBUG] File exists: {os.path.exists(filepath)}")

        ext = filepath.rsplit('.', 1)[1].lower()

        if ext == 'txt':
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as file_handle:
                return sanitize_text(file_handle.read())

        if ext == 'pdf':
            reader = PdfReader(filepath)
            pages_text = []
            for page in reader.pages:
                page_text = page.extract_text() or ''
                if page_text:
                    pages_text.append(page_text)
            return sanitize_text('\n\n'.join(pages_text))

        if ext == 'docx':
            # Graceful fallback: binary docx parsing is not supported without python-docx.
            return None

        if ext == 'doc':
            # Legacy .doc parsing is not supported in this service.
            return None

        return None
    except Exception as error:
        print(f"[ERROR] Error extracting text from {filepath}: {error}")
        import traceback
        traceback.print_exc()
        return None


def tokenize_text(text):
    """Tokenize text into lowercase words for lexical fallback ranking."""
    if not text:
        return []
    return [token for token in re.findall(r"\w+", text.lower()) if len(token) > 2]


def rank_chunk_records(question, chunk_records, k):
    """Simple lexical ranking fallback when vector retrieval is unavailable."""
    query_tokens = set(tokenize_text(question))
    if not query_tokens:
        return chunk_records[:k]

    scored = []
    question_lower = question.lower()

    for chunk in chunk_records:
        content = (chunk.get('content') or '').lower()
        if not content.strip():
            continue

        content_tokens = set(tokenize_text(content))
        overlap = len(query_tokens.intersection(content_tokens))
        phrase_bonus = 2 if question_lower in content else 0
        score = overlap + phrase_bonus

        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [chunk for _, chunk in scored[:k]]


def format_docs_for_llm(docs):
    """Format vector documents into one context block for LLM prompts."""
    formatted_string = ""
    for index, doc in enumerate(docs):
        source_filename = os.path.basename(doc.metadata.get('source', 'Unknown Source'))
        formatted_string += f"--- Context from {source_filename} (Chunk {index+1}) ---\n"
        formatted_string += doc.page_content.strip() + "\n\n"
    return formatted_string.strip()


def format_chunk_records_for_llm(chunks):
    """Format DB chunk records into one context block for LLM prompts."""
    parts = []
    for index, chunk in enumerate(chunks):
        source_filename = os.path.basename(chunk.get('source_file') or 'Unknown Source')
        parts.append(f"--- Context from {source_filename} (Chunk {index+1}) ---")
        parts.append((chunk.get('content') or '').strip())
        parts.append('')
    return "\n".join(parts).strip()
