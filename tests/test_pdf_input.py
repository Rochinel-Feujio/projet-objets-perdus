"""
Tests unitaires de la conversion PDF -> image (pdf_input.py) — un document
administratif peut arriver en PDF scanné plutôt qu'en photo JPG/PNG.

Lancer avec : python -m pytest tests/test_pdf_input.py -v
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pymupdf
from PIL import Image, ImageDraw, ImageFont

from pdf_input import is_pdf, pdf_first_page_to_image
from main import analyze_document


def _font(size=28):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _make_pdf(num_pages: int) -> str:
    """Construit un PDF de test à `num_pages` pages, chaque page contenant
    une image simple générée à la volée (pas besoin de vraie photo)."""
    img = Image.new("RGB", (300, 200), "white")
    fd_img, img_path = tempfile.mkstemp(suffix=".png")
    os.close(fd_img)
    img.save(img_path)

    doc = pymupdf.open()
    page_pdf = pymupdf.open(img_path).convert_to_pdf()
    single_page = pymupdf.open("pdf", page_pdf)
    for _ in range(num_pages):
        doc.insert_pdf(single_page)
    single_page.close()

    fd_pdf, pdf_path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd_pdf)
    doc.save(pdf_path)
    doc.close()
    os.unlink(img_path)
    return pdf_path


def test_is_pdf():
    assert is_pdf("document.pdf") is True
    assert is_pdf("document.PDF") is True
    assert is_pdf("photo.jpg") is False
    assert is_pdf("photo.png") is False


def test_pdf_first_page_to_image_single_page():
    pdf_path = _make_pdf(1)
    try:
        image_path, page_count = pdf_first_page_to_image(pdf_path)
        try:
            assert page_count == 1
            assert os.path.exists(image_path)
            with Image.open(image_path) as im:
                assert im.width > 0 and im.height > 0
        finally:
            os.unlink(image_path)
    finally:
        os.unlink(pdf_path)


def test_pdf_first_page_to_image_multi_page_reports_count():
    pdf_path = _make_pdf(3)
    try:
        image_path, page_count = pdf_first_page_to_image(pdf_path)
        try:
            assert page_count == 3
            assert os.path.exists(image_path)
        finally:
            os.unlink(image_path)
    finally:
        os.unlink(pdf_path)


def _make_cni_like_pdf() -> str:
    """PDF d'une page contenant un gabarit texte "CNI" (même principe que
    tests/generate_sample_images.py), pour vérifier que analyze_document()
    traite bien un PDF de bout en bout (conversion + OCR + classification)."""
    img = Image.new("RGB", (950, 600), "white")
    draw = ImageDraw.Draw(img)
    lines = [
        "REPUBLIQUE DU CAMEROUN",
        "CARTE NATIONALE D'IDENTITE",
        "NOM EXEMPLE",
        "Sexe: M   Taille: 1m75",
        "12345678901234567",
        "01/01/2000",
    ]
    y = 30
    for line in lines:
        draw.text((30, y), line, fill="black", font=_font(26))
        y += 60

    fd_img, img_path = tempfile.mkstemp(suffix=".png")
    os.close(fd_img)
    img.save(img_path)

    doc = pymupdf.open()
    page_pdf = pymupdf.open(img_path).convert_to_pdf()
    single_page = pymupdf.open("pdf", page_pdf)
    doc.insert_pdf(single_page)
    single_page.close()

    fd_pdf, pdf_path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd_pdf)
    doc.save(pdf_path)
    doc.close()
    os.unlink(img_path)
    return pdf_path


def test_analyze_document_accepts_pdf_end_to_end():
    """Un PDF scanné doit traverser tout le pipeline (prétraitement, OCR,
    classification, extraction) exactement comme une photo — sans rien
    enregistrer en base (analyze_document, pas process_document)."""
    pdf_path = _make_cni_like_pdf()
    try:
        result = analyze_document(pdf_path)
        assert result["type_document"] == "Carte Nationale d'Identité"
        assert result["champs"]["numero"] == "12345678901234567"
        # Une seule page : pas d'alerte "plusieurs pages".
        assert not any("pages" in alert for alert in result["alertes"])
    finally:
        os.unlink(pdf_path)


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    passed, failed = 0, 0
    for t in tests:
        try:
            t()
            print(f"OK   {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed} réussis, {failed} échoués")
    sys.exit(1 if failed else 0)
