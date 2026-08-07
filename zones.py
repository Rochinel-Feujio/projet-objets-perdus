"""
Extraction OCR par zones : au lieu de lire tout le texte de l'image en une
seule fois, on découpe des zones précises correspondant à la mise en page
connue de chaque type de document, et on lit l'OCR séparément sur chaque
zone. Plus précis qu'une lecture globale, car le texte d'une zone ne vient
pas polluer la reconnaissance d'un champ voisin (ex. confondre le nom et
l'en-tête "République du Cameroun").

Les coordonnées sont exprimées en fractions (0.0 à 1.0) de la largeur et de
la hauteur de l'image APRÈS correction de perspective (voir preprocessing.py)
— donc indépendantes de la résolution réelle de la photo envoyée.

État de calibration des zones :
  - CNI (format actuel), CNI_ANCIEN et Passeport : calibrées à partir de
    vraies photos de test envoyées pendant le développement.
  - Récépissé, Acte de naissance, Diplôme, Permis : estimées à partir du
    document de référence "Critères de différenciation" (aucune vraie photo
    testée pour ces types pour l'instant) — à corriger dès que des exemples
    réels seront disponibles, en ajustant simplement les 4 chiffres de la zone
    concernée ci-dessous.

À propos de CNI_ANCIEN : le classifieur (classifier.py) ne distingue pas
l'ancienne carte plastifiée de la carte biométrique actuelle — les deux sont
classées "CNI". read_zones() essaie donc automatiquement les deux mises en
page pour ce type de document (voir plus bas) et garde, champ par champ, la
première lecture non vide.

Ce module ne remplace jamais l'extraction existante (extractor.py) : si une
zone ne donne rien d'exploitable, l'appelant se rabat sur l'ancienne méthode
(lecture globale + heuristiques). Donc en cas de mauvaise calibration, le
résultat ne peut pas être pire qu'avant — seulement potentiellement meilleur.
"""

import cv2

from ocr import extract_text, DEFAULT_LANG

# Mode de segmentation Tesseract par champ : la plupart des zones ne
# contiennent qu'une seule ligne de valeur ("7"), mais la MRZ du passeport
# tient sur 2 lignes de longueur fixe ("6" = bloc de texte uniforme, garde
# les retours à la ligne au lieu de tout coller sur une seule ligne).
_ZONE_PSM = {"mrz": "6"}
_DEFAULT_ZONE_PSM = "7"

# (x_min, y_min, x_max, y_max) en fractions de l'image corrigée.
FIELD_ZONES = {
    "CNI": {
        "nom": (0.28, 0.16, 0.82, 0.29),
        "prenom": (0.28, 0.29, 0.82, 0.41),
        "date_naissance": (0.28, 0.41, 0.62, 0.52),
        "lieu_naissance": (0.28, 0.52, 0.82, 0.63),
        "sexe_taille": (0.28, 0.63, 0.82, 0.73),
    },
    # Ancienne carte plastifiée (photo principale à droite, puce et petite
    # photo à gauche) — calibrée sur une vraie photo envoyée pendant le
    # développement, mais uniquement par estimation visuelle des proportions
    # (pas encore vérifiée par une vraie passe OCR comme "CNI" et "PASSEPORT").
    # À affiner si les lectures réelles s'avèrent décalées.
    "CNI_ANCIEN": {
        "nom": (0.24, 0.24, 0.62, 0.31),
        "prenom": (0.24, 0.37, 0.62, 0.43),
        "date_naissance": (0.24, 0.485, 0.55, 0.545),
        "lieu_naissance": (0.24, 0.575, 0.62, 0.63),
        "sexe_taille": (0.24, 0.665, 0.62, 0.72),
    },
    "PASSEPORT": {
        "nom": (0.05, 0.27, 0.62, 0.37),
        "prenom": (0.05, 0.37, 0.62, 0.47),
        "date_naissance": (0.05, 0.47, 0.62, 0.57),
        "date_expiration": (0.05, 0.67, 0.62, 0.77),
        "mrz": (0.02, 0.85, 0.98, 1.00),
    },
    # Zones estimées (non calibrées sur photo réelle) :
    "RECEPISSE": {
        "numero": (0.08, 0.08, 0.92, 0.20),
        "nom": (0.10, 0.25, 0.90, 0.40),
    },
    "ACTE_NAISSANCE": {
        "nom": (0.10, 0.28, 0.90, 0.42),
        "date_naissance": (0.10, 0.42, 0.90, 0.55),
    },
    "DIPLOME": {
        "nom": (0.15, 0.38, 0.85, 0.53),
    },
    "PERMIS": {
        "nom": (0.28, 0.16, 0.82, 0.30),
        "date_naissance": (0.28, 0.30, 0.82, 0.42),
        "categories": (0.10, 0.58, 0.90, 0.84),
    },
}


def _crop_zone(image, box):
    h, w = image.shape[:2]
    x1, y1, x2, y2 = box
    px1, py1 = max(0, int(x1 * w)), max(0, int(y1 * h))
    px2, py2 = min(w, int(x2 * w)), min(h, int(y2 * h))
    if px2 <= px1 or py2 <= py1:
        return None
    crop = image[py1:py2, px1:px2]
    if crop.size == 0:
        return None
    # Agrandir la zone (x2) aide nettement l'OCR sur du texte de petite taille.
    return cv2.resize(crop, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)


def _read_zones_for_layout(image, zones: dict, lang: str) -> dict:
    results = {}
    for field_name, box in zones.items():
        crop = _crop_zone(image, box)
        if crop is None:
            continue
        psm = _ZONE_PSM.get(field_name, _DEFAULT_ZONE_PSM)
        # upscale=False : _crop_zone() a déjà agrandi x2 (voir plus haut) —
        # pas besoin (et pas intérêt) de remettre une couche d'agrandissement.
        text = extract_text(crop, lang=lang, psm=psm, upscale=False).strip()
        if text:
            results[field_name] = text
    return results


# Types de document pour lesquels plusieurs mises en page existent : on lit
# la mise en page principale, puis on complète avec la ou les mises en page
# alternatives pour tout champ resté vide.
_LAYOUT_VARIANTS = {
    "CNI": ["CNI", "CNI_ANCIEN"],
}


def read_zones(image, doc_type: str, lang: str = DEFAULT_LANG) -> dict:
    """Lit l'OCR séparément sur chaque zone connue pour ce type de document.

    Pour les types ayant plusieurs mises en page connues (ex. CNI actuelle vs
    ancienne carte plastifiée, voir _LAYOUT_VARIANTS), essaie chaque mise en
    page et garde, champ par champ, la première lecture non vide — le
    classifieur ne distinguant pas les variantes d'un même type de document.

    Retourne {nom_du_champ: texte_brut_lu}. Types de document sans zones
    définies -> dict vide (l'appelant se rabat alors entièrement sur la
    lecture globale existante)."""
    layouts = _LAYOUT_VARIANTS.get(doc_type, [doc_type])
    results = {}
    for layout in layouts:
        zones = FIELD_ZONES.get(layout, {})
        # Ne relit que les champs encore manquants : si la première mise en
        # page a déjà tout donné, on n'a pas besoin (et pas intérêt, pour la
        # vitesse) de relire les zones des mises en page alternatives.
        missing_zones = {k: v for k, v in zones.items() if k not in results}
        if not missing_zones:
            break
        layout_results = _read_zones_for_layout(image, missing_zones, lang)
        for field_name, text in layout_results.items():
            results.setdefault(field_name, text)
    return results


def first_line(text: str):
    """Garde la première ligne non vide d'un texte de zone (nettoyée)."""
    if not text:
        return None
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line
    return None