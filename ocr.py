"""
Extraction de texte par OCR (Tesseract).
"""

import os
import unicodedata

import numpy as np
import pytesseract
from PIL import Image

# Sur Windows, Tesseract n'est pas toujours dans le PATH après installation.
# On détecte automatiquement l'emplacement par défaut de l'installeur UB-Mannheim.
# Sur le serveur Ubuntu (installé via apt), Tesseract est déjà dans le PATH et
# ce bloc ne fait rien.
_WINDOWS_DEFAULT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.name == "nt" and os.path.isfile(_WINDOWS_DEFAULT_PATH):
    pytesseract.pytesseract.tesseract_cmd = _WINDOWS_DEFAULT_PATH


def _to_pil_image(image):
    """Accepte soit un chemin de fichier (str), soit une image déjà en mémoire
    (PIL.Image, ou tableau numpy au format OpenCV/BGR) — utile pour lire l'OCR
    directement sur l'image déjà prétraitée (redressée, recadrée) plutôt que
    sur le fichier original brut."""
    if isinstance(image, str):
        return Image.open(image)
    if isinstance(image, Image.Image):
        return image
    if isinstance(image, np.ndarray):
        import cv2
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)
    raise TypeError(f"Type d'image non supporté pour l'OCR : {type(image)}")


def extract_text(image, lang: str = "fra") -> str:
    """Lit tout le texte visible sur l'image. `image` peut être un chemin de
    fichier ou une image déjà chargée (PIL ou tableau numpy)."""
    pil_image = _to_pil_image(image)
    raw_text = pytesseract.image_to_string(pil_image, lang=lang)
    return raw_text


def normalize_text(text: str) -> str:
    """Minuscules + suppression des accents, pour faciliter la recherche de
    mots-clés indépendamment de la casse/accentuation lue par l'OCR."""
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def extract_text_normalized(image, lang: str = "fra") -> str:
    return normalize_text(extract_text(image, lang=lang))