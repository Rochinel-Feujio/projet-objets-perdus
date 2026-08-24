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


def pdf_first_page_to_image(pdf_path: str, dpi: int = 220):
    """Convertit la première page du PDF en image PNG (fichier temporaire,
    à supprimer par l'appelant après usage) et renvoie
    (chemin_image_png, nombre_total_de_pages_du_pdf).

    dpi=220 est un compromis raisonnable entre netteté (utile pour l'OCR) et
    taille/temps de traitement — largement suffisant pour un document A4 ou
    une carte scannée."""
    doc = pymupdf.open(pdf_path)
    try:
        page_count = doc.page_count
        if page_count == 0:
            raise ValueError("Le fichier PDF ne contient aucune page.")

        page = doc.load_page(0)
        zoom = dpi / 72  # 72 dpi = résolution de référence PDF
        matrix = pymupdf.Matrix(zoom, zoom)
        pixmap = page.get_pixmap(matrix=matrix)

        fd, image_path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        pixmap.save(image_path)
        return image_path, page_count
    finally:
        doc.close()
