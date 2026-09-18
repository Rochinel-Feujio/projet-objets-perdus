"""
Extraction de texte par OCR (PaddleOCR).

Anciennement basé sur Tesseract (voir historique git) : remplacé par
PaddleOCR, un moteur par deep learning nettement plus robuste sur des
photos réelles imparfaites (angle, flou, faible luminosité) — voir
ocr_benchmark/RAPPORT_PaddleOCR_vs_Tesseract.md pour les chiffres qui ont
motivé ce choix.

Le reste du pipeline (classifier.py, zones.py, extractor.py, validator.py)
n'a pas besoin de changer : extract_text(), normalize_text() et
extract_text_normalized() gardent exactement la même signature qu'avant.
"""

import unicodedata

import cv2
import numpy as np
from PIL import Image

# PaddleOCR ne propose pas de combiner deux langues comme le "fra+eng" utilisé
# avant avec Tesseract : un seul code de langue est utilisé par appel. "fr"
# charge le modèle de reconnaissance pour l'alphabet latin élargi (accents
# français inclus), qui reconnaît les caractères un par un plutôt que des
# mots d'un dictionnaire figé — les mots anglais mélangés aux documents
# camerounais bilingues (ex. "NOM/SURNAME") restent donc lisibles aussi.
DEFAULT_LANG = "fr"

# Taille cible du plus grand côté avant OCR : les photos de documents ont
# souvent du texte petit. Un texte trop petit en pixels est la cause la plus
# fréquente d'une lecture OCR incomplète — l'agrandir change beaucoup (vrai
# pour un moteur par règles comme Tesseract, et toujours utile pour un
# moteur par deep learning comme PaddleOCR).
_MIN_LONG_SIDE = 1600

# Un objet PaddleOCR charge des modèles de réseaux de neurones à sa création
# (opération lente, ~quelques secondes) : on le crée une seule fois et on le
# réutilise, plutôt que d'en recréer un à chaque appel d'extract_text().
# Le tout premier appel télécharge aussi les modèles (quelques dizaines de
# Mo) si nécessaire — connexion internet requise à ce moment-là seulement.
_engine_cache = {}


def get_engine(lang: str):
    if lang not in _engine_cache:
        from paddleocr import PaddleOCR

        _engine_cache[lang] = PaddleOCR(
            lang=lang,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=True,
        )
    return _engine_cache[lang]


def _to_bgr_array(image):
    """Accepte soit un chemin de fichier (str), soit une image déjà en
    mémoire (PIL.Image, ou tableau numpy déjà au format OpenCV/BGR utilisé
    partout ailleurs dans le pipeline) — renvoie toujours un tableau numpy
    BGR, le format attendu par PaddleOCR (comme OpenCV)."""
    if isinstance(image, str):
        loaded = cv2.imread(image)
        if loaded is None:
            raise ValueError(f"Impossible de lire l'image : {image}")
        return loaded
    if isinstance(image, Image.Image):
        rgb = np.array(image.convert("RGB"))
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    if isinstance(image, np.ndarray):
        return image
    raise TypeError(f"Type d'image non supporté pour l'OCR : {type(image)}")


def _upscale_if_small(img_bgr):
    """Agrandit l'image si son plus grand côté est petit — un texte fin a
    besoin de plus de pixels pour être bien reconnu, quel que soit le
    moteur OCR utilisé."""
    h, w = img_bgr.shape[:2]
    long_side = max(w, h)
    if long_side >= _MIN_LONG_SIDE or long_side == 0:
        return img_bgr
    scale = _MIN_LONG_SIDE / long_side
    new_size = (int(w * scale), int(h * scale))
    return cv2.resize(img_bgr, new_size, interpolation=cv2.INTER_LANCZOS4)


def extract_text(image, lang: str = DEFAULT_LANG, psm: str = None, upscale: bool = True) -> str:
    """Lit le texte visible sur l'image. `image` peut être un chemin de
    fichier ou une image déjà chargée (PIL ou tableau numpy BGR).

    `psm` : conservé uniquement pour compatibilité avec les appels existants
    (zones.py notamment, qui distinguait "une seule ligne" vs "bloc de texte
    MRZ" pour Tesseract). PaddleOCR détecte lui-même les lignes de texte
    quelle que soit la mise en page — ce paramètre n'a donc plus d'effet ici,
    mais est laissé dans la signature pour ne rien casser ailleurs dans le
    pipeline.

    `upscale` : mettre à False si l'appelant a déjà agrandi l'image lui-même
    (ex. zones.py fait déjà un resize x2 sur ses petits recadrages) — cumuler
    les deux agrandissements ralentit l'OCR pour rien."""
    img_bgr = _to_bgr_array(image)
    if upscale:
        img_bgr = _upscale_if_small(img_bgr)

    engine = get_engine(lang)
    results = engine.predict(img_bgr)

    lines = []
    for res in results:
        rec_texts = res.get("rec_texts") if isinstance(res, dict) else getattr(res, "rec_texts", None)
        rec_boxes = res.get("rec_boxes") if isinstance(res, dict) else getattr(res, "rec_boxes", None)
        if not rec_texts:
            continue
        if rec_boxes is not None and len(rec_boxes) == len(rec_texts):
            # Trie par position verticale (haut -> bas) pour reconstituer un
            # ordre de lecture cohérent, comme le ferait une lecture humaine.
            order = sorted(range(len(rec_texts)), key=lambda i: rec_boxes[i][1])
            lines.extend(rec_texts[i] for i in order)
        else:
            lines.extend(rec_texts)

    return "\n".join(lines)


def normalize_text(text: str) -> str:
    """Minuscules + suppression des accents, pour faciliter la recherche de
    mots-clés indépendamment de la casse/accentuation lue par l'OCR."""
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def extract_text_normalized(image, lang: str = DEFAULT_LANG) -> str:
    return normalize_text(extract_text(image, lang=lang))
