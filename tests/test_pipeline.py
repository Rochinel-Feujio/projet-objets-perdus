"""
Tests unitaires du pipeline (classification, extraction, validation)
— ne nécessitent pas d'image réelle : ils simulent le texte OCR normalisé.

Lancer avec : python -m pytest tests/ -v
(ou : python tests/test_pipeline.py)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from classifier import classify
from extractor import extract_fields
from validator import validate


def test_classify_cni():
    text = "republique du cameroun carte nationale d'identite sexe m taille 1m75"
    result = classify(image_ratio=1.586, ocr_text_normalized=text)
    assert result.doc_type == "CNI", result.scores


def test_classify_permis():
    text = "permis de conduire categorie a b c ministere des transports"
    result = classify(image_ratio=1.586, ocr_text_normalized=text)
    assert result.doc_type == "PERMIS", result.scores


def test_classify_passeport_via_mrz():
    text = "passeport republic of cameroon p<cmrnom<<prenom<<<<<<<<<<<<<<<<<<<<<<"
    result = classify(image_ratio=0.83, ocr_text_normalized=text)
    assert result.doc_type == "PASSEPORT", result.scores


def test_classify_acte_naissance():
    text = "republique du cameroun paix - travail - patrie extrait acte de naissance officier etat civil"
    result = classify(image_ratio=0.707, ocr_text_normalized=text)
    assert result.doc_type == "ACTE_NAISSANCE", result.scores


def test_classify_recepisse():
    text = "recepisse titre d'identite provisoire delegation generale surete nationale"
    result = classify(image_ratio=0.707, ocr_text_normalized=text)
    assert result.doc_type == "RECEPISSE", result.scores


def test_classify_diplome():
    text = "diplome de licence universite baccalaureat mention atteste"
    result = classify(image_ratio=1.414, ocr_text_normalized=text)
    assert result.doc_type == "DIPLOME", result.scores


def test_extract_niu_cni():
    raw = "NOM EXEMPLE\n12345678901234567\n01/01/2000"
    fields = extract_fields("CNI", raw, raw.lower())
    assert fields["numero"] == "12345678901234567"
    assert fields["date_naissance"] == "01/01/2000"


def test_classify_cni_ancienne_republique_unie():
    # Génération 1972-1984 : en-tête "RÉPUBLIQUE UNIE DU CAMEROUN", jamais
    # "RÉPUBLIQUE DU CAMEROUN" seul — doit quand même être reconnue comme CNI
    # (voir le groupe d'alternatives sur l'en-tête républicain dans config.py).
    text = "republique unie du cameroun carte nationale d'identite sexe m taille 1m75"
    result = classify(image_ratio=1.586, ocr_text_normalized=text)
    assert result.doc_type == "CNI", result.scores


def test_classify_cni_ancienne_republique_federale():
    # Génération 1964-1972 : en-tête "RÉPUBLIQUE FÉDÉRALE DU CAMEROUN".
    text = "republique federale du cameroun carte nationale identity card sexe taille"
    result = classify(image_ratio=1.586, ocr_text_normalized=text)
    assert result.doc_type == "CNI", result.scores


def test_classify_cni_generation_1984_1999():
    # Génération 1984-1999 : en-tête "REPUBLIC OF CAMEROON / RÉPUBLIQUE DU
    # CAMEROUN" (encore en carton, avant la carte informatisée Teslin de
    # 1999/2008) — même libellé républicain que toutes les générations
    # suivantes, donc déjà couvert par le groupe d'alternatives, mais gardé
    # comme cas explicite pour documenter cette génération précise.
    text = "republique du cameroun republic of cameroon carte nationale d'identite sexe f taille 1m60"
    result = classify(image_ratio=1.586, ocr_text_normalized=text)
    assert result.doc_type == "CNI", result.scores


def test_classify_cni_nouvelle_carte_2025():
    # Nouvelle carte biométrique Augentic (depuis 2025) : même en-tête
    # "RÉPUBLIQUE DU CAMEROUN" que la génération biométrique précédente — pas
    # de mots-clés spécifiques connus pour l'instant (mise en page non
    # calibrée, voir zones.py), mais doit être reconnue comme CNI comme
    # n'importe quelle autre génération.
    text = "republique du cameroun national identity card carte nationale d'identite sexe f taille 1m60"
    result = classify(image_ratio=1.586, ocr_text_normalized=text)
    assert result.doc_type == "CNI", result.scores


def test_classify_cni_not_confused_with_passeport_by_bilingual_header():
    # En-tête bilingue présent sur une vraie CNI camerounaise ("RÉPUBLIQUE DU
    # CAMEROUN / REPUBLIC OF CAMEROON") : ne doit pas faire basculer la
    # classification vers PASSEPORT juste parce que "republic of cameroon"
    # apparaît dans le texte — repéré sur un vrai récépissé/CNI envoyé par un
    # utilisateur, mal lu par l'OCR, où ce chevauchement de mots-clés faisait
    # basculer à tort la classification vers "Passeport".
    text = "republique du cameroun republic of cameroon nom prenoms sexe taille"
    result = classify(image_ratio=1.60, ocr_text_normalized=text)
    assert result.doc_type == "CNI", result.scores


def test_extract_date_with_dot_separator():
    # Les vraies CNI camerounaises utilisent souvent des dates au format
    # "26.10.1965" (point) plutôt que "/" ou "-" — un vrai document envoyé
    # par un utilisateur avait une date parfaitement lisible par l'OCR mais
    # ignorée par l'extraction faute de séparateur reconnu.
    raw = "NOM EXEMPLE\n12345678901234567\n26.10.1965"
    fields = extract_fields("CNI", raw, raw.lower())
    assert fields["date_naissance"] == "26/10/1965"


def test_validate_flags_bad_niu():
    fields = {"type_document": "CNI", "numero": "123", "nom": "NOM EXEMPLE"}
    alerts = validate("CNI", fields)
    assert any("17 chiffres" in a for a in alerts)


def test_validate_ok_niu():
    fields = {"type_document": "CNI", "numero": "12345678901234567", "nom": "NOM EXEMPLE"}
    alerts = validate("CNI", fields)
    assert not any("17 chiffres" in a for a in alerts)


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
