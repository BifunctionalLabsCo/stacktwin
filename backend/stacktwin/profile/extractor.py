import re
from pathlib import Path
import hashlib


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract raw text from a PDF file (CV or LinkedIn export).
    Returns plain text string.
    """
    try:
        import pypdf
        reader = pypdf.PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return _clean_text(text)
    except Exception as e:
        raise ValueError(f"Failed to extract text from PDF: {e}")


def extract_text_from_string(raw: str) -> str:
    """
    Accept plain text directly for manual input fallback.
    """
    return _clean_text(raw)


def extract_text_from_file(file_path: str) -> str:
    """
    Router that decides extraction method based on file type.
    Extend this as we support more formats (docx, txt etc).
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = path.suffix.lower()

    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext == ".txt":
        return path.read_text(encoding="utf-8")
    else:
        raise ValueError(f"Unsupported file type: {ext}. Supported: .pdf, .txt")


def _clean_text(text: str) -> str:
    """
    Remove excessive whitespace and non-printable characters.
    """
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\x20-\x7E\n]', '', text)
    return text.strip()

def hash_cv_content(content: bytes) -> str:
    """
    Stable hash of raw CV file bytes.
    Same file uploaded twice produces the same hash, regardless of filename.
    Used to detect identical re-uploads and skip redundant Nebius calls.
    """
    return hashlib.sha256(content).hexdigest()[:16]
