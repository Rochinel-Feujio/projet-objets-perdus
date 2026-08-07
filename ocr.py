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

# Les documents camerounais sont bilingues (ex. "NOM/SURNAME") : lire avec
# "fra" seul fait rater ou déformer les mots anglais (et inversement). "eng"
# est déjà inclus par défaut dans le paquet tesseract-ocr, donc pas besoin de
# rien installer de plus en combinant les deux.
DEFAULT_LANG = "fra+eng"

# Taille cible du plus grand côté avant OCR : les photos de documents ont
# souvent du texte petit. Un texte trop petit en pixels est la cause la plus
# fréquente d'une lecture OCR incomplète — l'agrandir change beaucoup.
_MIN_LONG_SIDE = 1600


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


def _upscale_if_small(pil_image: Image.Image) -> Image.Image:
    """Agrandit l'image si son plus grand côté est petit — Tesseract lit
    nettement mieux du texte fin quand il a plus de pixels à analyser."""
    w, h = pil_image.size
    long_side = max(w, h)
    if long_side >= _MIN_LONG_SIDE or long_side == 0:
        return pil_image
    scale = _MIN_LONG_SIDE / long_side
    new_size = (int(w * scale), int(h * scale))
    return pil_image.resize(new_size, Image.LANCZOS)


def extract_text(image, lang: str = DEFAULT_LANG, psm: str = None, upscale: bool = True) -> str:
    """Lit le texte visible sur l'image. `image` peut être un chemin de
    fichier ou une image déjà chargée (PIL ou tableau numpy).

    `psm` (page segmentation mode Tesseract) :
      - Si précisé (ex. "7" = une seule ligne, utilisé par zones.py pour de
        petits recadrages de champ) : une seule passe avec cette valeur.
      - Si None (lecture globale d'un document entier) : essaie plusieurs
        modes de segmentation ("3" = mise en page automatique, "6" = bloc de
        texte uniforme) et garde le résultat le plus long — une image de
        document a une mise en page trop variée pour qu'un seul mode soit
        toujours le meilleur, et un mode inadapté est la cause la plus
        fréquente d'un texte "incomplet" (des blocs entiers sautés).

    `upscale` : mettre à False si l'appelant a déjà agrandi l'image lui-même
    (ex. zones.py fait déjà un resize x2 sur ses petits recadrages) — cumuler
    les deux agrandissements ralentit énormément l'OCR pour rien, voire nuit
    à la lecture (flou d'interpolation) sans gain de précision."""
    pil_image = _to_pil_image(image)
    if upscale:
        pil_image = _upscale_if_small(pil_image)

    if psm is not None:
        config = f"--psm {psm}"
        return pytesseract.image_to_string(pil_image, lang=lang, config=config)

    best_text = ""
    for candidate_psm in ("3", "6"):
        config = f"--psm {candidate_psm}"
        try:
            text = pytesseract.image_to_string(pil_image, lang=lang, config=config)
        except pytesseract.TesseractError:
            continue
        if len(text.strip()) > len(best_text.strip()):
            best_text = text
    return best_text


def normalize_text(text: str) -> str:
    """Minuscules + suppression des accents, pour faciliter la recherche de
    mots-clés indépendamment de la casse/accentuation lue par l'OCR."""
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def extract_text_normalized(image, lang: str = DEFAULT_LANG) -> str:
    return normalize_text(extract_text(image, lang=lang))