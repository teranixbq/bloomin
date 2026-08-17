import re
import httpx

def _gdrive_direct_url(url: str) -> str:
    match = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
    if match:
        file_id = match.group(1)
        return f"https://drive.google.com/uc?export=download&id={file_id}"
    return url

def load_corpus(source: str) -> str:
    """Fetch corpus teks dari URL atau file lokal, return sebagai string."""
    if source.startswith("http://") or source.startswith("https://"):
        url = _gdrive_direct_url(source)
        with httpx.Client(follow_redirects=True, timeout=15) as client:
            resp = client.get(url)
            resp.raise_for_status()
            text = resp.text
    else:
        with open(source, "r", encoding="utf-8") as f:
            text = f.read()
    print(f"[corpus] Loaded {len(text)} chars from: {source}")
    return text
