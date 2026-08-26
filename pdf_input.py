"""
Support des documents envoyés au format PDF (plutôt qu'une photo JPG/PNG) :
une administration ou une personne peut avoir un scan PDF de son document
plutôt qu'une photo. On convertit la première page du PDF en image, puis on
réutilise exactement le même pipeline de détection (OCR, classification,
extraction) que pour une photo classique — aucun changement nécessaire côté
classifier.py / extractor.py / zones.py.

Nécessite PyMuPDF (`pip install PyMuPDF`, module `pymupdf`, anciennement
importé sous le nom `fitz`) — voir requirements.txt.
"""

import os
import tempfile

import pymupdf


def is_pdf(file_path: str) -> bool:
    return os.path.splitext(file_path)[1].lower() == ".pdf"


def _extract_dominant_embedded_image(doc, page):
    """Cas très fréquent avec les CNI/récépissés : la personne a pris la carte
    en photo avec une appli mobile ("scanner") qui a directement exporté un
    PDF d'une seule page contenant cette photo en pleine page, sans texte ni
    vecteur additionnel. Dans ce cas, on récupère le fichier image original
    intégré tel quel plutôt que de le faire repasser par le moteur de rendu
    PDF (`get_pixmap`).

    Pourquoi c'est important : `get_pixmap(matrix=...)` rend la page à une
    résolution cible en POINTS PDF (dpi/72), indépendamment de la résolution
    réelle de l'image intégrée. Beaucoup de ces PDF générés par appli mobile
    déclarent une taille de page en points qui correspond en fait 1 pour 1 aux
    pixels de la photo (donc ~72 dpi "apparent"), alors que demander un rendu
    à 220 dpi force PyMuPDF à agrandir cette image par interpolation d'un
    facteur ~3x. Résultat : une image bien plus grande en pixels mais SANS
    aucun détail supplémentaire, ce qui dégrade fortement le score de netteté
    (variance du Laplacien) et gêne l'OCR — un problème observé concrètement
    sur de vrais récépissés envoyés par les utilisateurs (score de netteté
    ~2/80 alors que la photo d'origine était parfaitement lisible). Réutiliser
    directement les pixels d'origine évite ce faux agrandissement.

    Retourne le chemin d'un fichier temporaire contenant l'image d'origine,
    ou None si la page ne correspond pas à ce cas simple (aucune image, ou
    plusieurs images/contenu mixte — auquel cas l'appelant se rabat sur le
    rendu classique de la page)."""
    images = page.get_images(full=True)
    if len(images) != 1:
        return None

    xref = images[0][0]
    try:
        base = doc.extract_image(xref)
    except Exception:
        return None

    width = base.get("width", 0)
    height = base.get("height", 0)
    image_bytes = base.get("image")
    if not width or not height or not image_bytes:
        return None
    # Trop petite pour être exploitable par l'OCR : mieux vaut le rendu
    # classique (qui pourra au moins l'agrandir de façon prévisible).
    if width < 500 or height < 500:
        return None

    ext = base.get("ext") or "png"
    fd, image_path = tempfile.mkstemp(suffix=f".{ext}")
    os.close(fd)
    with open(image_path, "wb") as f:
        f.write(image_bytes)
    return image_path


def pdf_first_page_to_image(pdf_path: str, dpi: int = 220):
    """Convertit la première page du PDF en image (fichier temporaire,
    à supprimer par l'appelant après usage) et renvoie
    (chemin_image, nombre_total_de_pages_du_pdf).

    Si la page est essentiellement une seule photo plaquée en pleine page
    (voir `_extract_dominant_embedded_image`), on récupère cette image telle
    quelle plutôt que de la refaire passer par le moteur de rendu PDF, pour
    ne pas l'agrandir artificiellement par interpolation. Sinon, on rend la
    page à `dpi` (220 par défaut) : un compromis raisonnable entre netteté
    (utile pour l'OCR) et taille/temps de traitement pour un vrai contenu PDF
    (texte, tableaux...)."""
    doc = pymupdf.open(pdf_path)
    try:
        page_count = doc.page_count
        if page_count == 0:
            raise ValueError("Le fichier PDF ne contient aucune page.")

        page = doc.load_page(0)

        raw_image_path = _extract_dominant_embedded_image(doc, page)
        if raw_image_path is not None:
            return raw_image_path, page_count

        zoom = dpi / 72  # 72 dpi = résolution de référence PDF
        matrix = pymupdf.Matrix(zoom, zoom)
        pixmap = page.get_pixmap(matrix=matrix)

        fd, image_path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        pixmap.save(image_path)
        return image_path, page_count
    finally:
        doc.close()
