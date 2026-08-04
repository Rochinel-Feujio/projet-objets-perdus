"""
Extraction de texte par OCR (Tesseract).
"""

import os
import pytesseract
from PIL import Image

_WINDOWS_DEFAULT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.name == "nt" and os.path.isfile(_WINDOWS_DEFAULT_PATH):
    pytesseract.pytesseract.tesseract_cmd = _WINDOWS_DEFAULT_PATH


def extract_text(image_path: str, lang: str = "fra") -> str:
    image = Image.open(image_path)
    raw_text = pytesseract.image_to_string(image, lang=lang)
    return raw_text


def extract_text_normalized(image_path: str, lang: str = "fra") -> str:
    text = extract_text(image_path, lang=lang)
    return _normalize(text)


def _normalize(text: str) -> str:
    import unicodedata
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text