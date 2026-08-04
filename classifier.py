"""
Classification du type de document — approche hybride (v1, sans modèle entraîné) :

  1. Signal "format" : ratio largeur/hauteur de l'image -> carte / A4 portrait / A4 paysage.
  2. Signal "OCR" : présence de mots-clés propres à chaque type + zone MRZ pour le passeport
     + tableau de catégories A/B/C/D/E pour le permis.

Chaque type de document reçoit un score ; le type avec le meilleur score est retenu,
avec un niveau de confiance. Cette approche ne nécessite AUCUN jeu de données
d'entraînement — elle peut fonctionner dès le premier jour. Elle sera remplacée /
complétée par un CNN (transfer learning) dès qu'un dataset d'images labellisées
sera disponible (voir README).
"""

import re
from dataclasses import dataclass, field

from config import (
    DOCUMENT_TYPES,
    CARD_RATIO_RANGE,
    A4_PORTRAIT_RATIO_RANGE,
    A4_LANDSCAPE_RATIO_RANGE,
    PASSPORT_PAGE_RATIO_RANGE,
    MRZ_LINE_REGEX,
)


@dataclass
class ClassificationResult:
    doc_type: str
    label: str
    confidence: float
    scores: dict = field(default_factory=dict)
    mrz_detected: bool = False


def _format_from_ratio(ratio: float) -> str:
    if CARD_RATIO_RANGE[0] <= ratio <= CARD_RATIO_RANGE[1]:
        return "card"
    if PASSPORT_PAGE_RATIO_RANGE[0] <= ratio <= PASSPORT_PAGE_RATIO_RANGE[1]:
        return "passport_page"
    if A4_PORTRAIT_RATIO_RANGE[0] <= ratio <= A4_PORTRAIT_RATIO_RANGE[1]:
        return "a4_portrait"
    if A4_LANDSCAPE_RATIO_RANGE[0] <= ratio <= A4_LANDSCAPE_RATIO_RANGE[1]:
        return "a4_landscape"
    return "unknown"


def _detect_mrz(ocr_text_normalized: str) -> bool:
    lines = [l.strip().upper() for l in ocr_text_normalized.splitlines() if l.strip()]
    hits = [l for l in lines if re.fullmatch(MRZ_LINE_REGEX, l.replace(" ", ""))]
    return len(hits) >= 1 or "p<cmr" in ocr_text_normalized.replace(" ", "")


def _detect_category_table(ocr_text_normalized: str) -> bool:
    # Recherche grossière d'un tableau de catégories de permis (A, B, C, D, E proches les uns des autres)
    letters_found = sum(1 for l in ["a", "b", "c", "d", "e"] if re.search(rf"\b{l}\b", ocr_text_normalized))
    return letters_found >= 3 and "categorie" in ocr_text_normalized


def classify(image_ratio: float, ocr_text_normalized: str) -> ClassificationResult:
    doc_format = _format_from_ratio(image_ratio)
    mrz_detected = _detect_mrz(ocr_text_normalized)
    category_table_detected = _detect_category_table(ocr_text_normalized)

    scores = {}
    for doc_type, cfg in DOCUMENT_TYPES.items():
        score = 0.0

        # Signal format (poids 0.4)
        if doc_format in cfg["formats"]:
            score += 0.4
        elif doc_format == "unknown":
            score += 0.1  # neutre, ne pénalise pas trop si le cadrage est imparfait

        # Signal mots-clés (poids 0.5, proportionnel au nombre de mots-clés trouvés)
        keywords = cfg["keywords"]
        found = sum(1 for kw in keywords if kw in ocr_text_normalized)
        if keywords:
            score += 0.5 * (found / len(keywords))

        # Pénalité si des mots-clés d'exclusion apparaissent (ex. "permis" trouvé alors qu'on évalue CNI)
        exclude = cfg.get("exclude_keywords", [])
        excluded_found = sum(1 for kw in exclude if kw in ocr_text_normalized)
        score -= 0.3 * excluded_found

        # Signaux spécifiques
        if doc_type == "PASSEPORT" and mrz_detected:
            score += 0.3
        if doc_type == "PERMIS" and category_table_detected:
            score += 0.3
        if doc_type == "CNI" and category_table_detected:
            score -= 0.3  # une carte avec tableau de catégories est probablement un permis, pas une CNI

        scores[doc_type] = max(score, 0.0)

    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]
    total = sum(scores.values()) or 1.0
    confidence = best_score / total if total > 0 else 0.0

    return ClassificationResult(
        doc_type=best_type,
        label=DOCUMENT_TYPES[best_type]["label"],
        confidence=round(confidence, 2),
        scores={k: round(v, 2) for k, v in scores.items()},
        mrz_detected=mrz_detected,
    )
