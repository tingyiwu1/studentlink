import unicodedata
from functools import partial

def normalize(text: str) -> str:
    if not isinstance(text, str):
        return None
    return unicodedata.normalize("NFKD", text).strip()