"""
Tests d'intégration du branchement IA de vision dans main.analyze_document()
— vérifie que la DÉCISION d'appeler l'IA et la FUSION de son résultat avec
les champs déjà lus par l'OCR se comportent comme prévu, sans jamais
appeler la vraie API Mistral (main.ai_vision_configured et
main.extract_fields_with_ai sont simulés via monkeypatch).

Lancer avec : python -m pytest tests/test_main_ai_fallback.py -v
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image, ImageDraw, ImageFont

import main


def _font(size=28):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _make_cni_image() -> str:
    """Même gabarit texte que tests/generate_sample_images.py — une CNI que
    l'OCR local lit correctement (nom, numéro, date présents), pour tester
    la fusion IA sur une base connue plutôt que sur un pipeline OCR
    imprévisible."""
    img = Image.new("RGB", (950, 600), "white")
    draw = ImageDraw.Draw(img)
    lines = [
        "REPUBLIQUE DU CAMEROUN",
        "CARTE NATIONALE D'IDENTITE",
        "NOM EXEMPLE",
        "Sexe: M   Taille: 1m75",
        "12345678901234567",
        "Ne le 01/01/2000",
        "Expire le 01/01/2030",
    ]
    y = 30
    for line in lines:
        draw.text((30, y), line, fill="black", font=_font(26))
        y += 40
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    img.save(path)
    return path


def test_ai_not_called_when_not_configured(monkeypatch):
    """Si l'IA n'est pas configurée, elle ne doit jamais être sollicitée —
    comportement strictement identique à avant l'ajout de cette fonctionnalité."""
    monkeypatch.setattr(main, "ai_vision_configured", lambda: False)

    called = {"count": 0}

    def _should_not_be_called(*args, **kwargs):
        called["count"] += 1
        return None

    monkeypatch.setattr(main, "extract_fields_with_ai", _should_not_be_called)

    image_path = _make_cni_image()
    try:
        result = main.analyze_document(image_path)
        assert called["count"] == 0
        assert result["champs"]["numero"] == "12345678901234567"
    finally:
        os.unlink(image_path)


def _make_cni_image_without_expiration() -> str:
    """Même gabarit, mais une seule date (naissance) : extractor.extract_fields
    ne peut alors pas remplir "date_expiration" (nécessite 2 dates trouvées),
    ce qui donne un champ manquant naturel pour tester le complément IA."""
    img = Image.new("RGB", (950, 600), "white")
    draw = ImageDraw.Draw(img)
    lines = [
        "REPUBLIQUE DU CAMEROUN",
        "CARTE NATIONALE D'IDENTITE",
        "NOM EXEMPLE",
        "Sexe: M   Taille: 1m75",
        "12345678901234567",
        "Ne le 01/01/2000",
    ]
    y = 30
    for line in lines:
        draw.text((30, y), line, fill="black", font=_font(26))
        y += 40
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    img.save(path)
    return path


def test_ai_fills_missing_field_and_adds_alert(monkeypatch):
    """Si l'IA est configurée et sollicitée (on force le déclenchement via
    un seuil de confiance impossible à atteindre), un champ manquant après
    l'OCR doit être complété par sa réponse, avec une alerte de traçabilité."""
    monkeypatch.setattr(main, "ai_vision_configured", lambda: True)
    monkeypatch.setattr(main, "AI_FALLBACK_CONFIDENCE_THRESHOLD", 2.0)  # toujours déclenché

    def _fake_extract(image_path, type_document_label, field_keys):
        assert os.path.exists(image_path)
        assert type_document_label == "Carte Nationale d'Identité"
        champs = {k: None for k in field_keys}
        if "date_expiration" in champs:
            champs["date_expiration"] = "01/01/2031"  # absent de ce gabarit (une seule date)
        return {
            "champs": champs,
            "confiance": 0.8,
            "remarques": ["numéro difficile à lire, à vérifier manuellement"],
        }

    monkeypatch.setattr(main, "extract_fields_with_ai", _fake_extract)

    image_path = _make_cni_image_without_expiration()
    try:
        result = main.analyze_document(image_path)
        # Champ manquant après l'OCR, complété par l'IA :
        assert result["champs"]["date_expiration"] == "01/01/2031"
        # Champ déjà lu par l'OCR : ne doit PAS être écrasé par l'IA.
        assert result["champs"]["numero"] == "12345678901234567"
        # Traçabilité dans les alertes :
        assert any("date_expiration" in a and "IA de vision" in a for a in result["alertes"])
        assert any("numéro difficile à lire" in a for a in result["alertes"])
    finally:
        os.unlink(image_path)


def test_ai_does_not_overwrite_existing_field(monkeypatch):
    """Même si l'IA renvoie une valeur différente pour un champ déjà rempli
    par l'OCR, on ne doit jamais l'écraser silencieusement (transparence :
    seuls les champs manquants sont complétés)."""
    monkeypatch.setattr(main, "ai_vision_configured", lambda: True)
    monkeypatch.setattr(main, "AI_FALLBACK_CONFIDENCE_THRESHOLD", 2.0)

    def _fake_extract(image_path, type_document_label, field_keys):
        return {
            "champs": {k: "VALEUR_IA_DIFFERENTE" for k in field_keys},
            "confiance": 0.9,
            "remarques": [],
        }

    monkeypatch.setattr(main, "extract_fields_with_ai", _fake_extract)

    image_path = _make_cni_image()
    try:
        result = main.analyze_document(image_path)
        assert result["champs"]["numero"] == "12345678901234567"
        assert result["champs"]["nom"] != "VALEUR_IA_DIFFERENTE"
    finally:
        os.unlink(image_path)


def test_ai_failure_does_not_break_analysis(monkeypatch):
    """Si extract_fields_with_ai renvoie None (échec/API indisponible),
    l'analyse doit se terminer normalement, sans alerte IA en trop."""
    monkeypatch.setattr(main, "ai_vision_configured", lambda: True)
    monkeypatch.setattr(main, "AI_FALLBACK_CONFIDENCE_THRESHOLD", 2.0)
    monkeypatch.setattr(main, "extract_fields_with_ai", lambda *a, **k: None)

    image_path = _make_cni_image()
    try:
        result = main.analyze_document(image_path)
        assert result["champs"]["numero"] == "12345678901234567"
        assert not any("IA de vision" in a for a in result["alertes"])
    finally:
        os.unlink(image_path)


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
