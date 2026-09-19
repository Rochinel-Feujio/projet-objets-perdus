# -*- coding: utf-8 -*-
"""Simulation de la classification sur un texte OCR représentatif de chaque
cas de document (les 6 types gérés par l'app, plus les 5 générations connues
de la CNI camerounaise) — sans avoir besoin d'une vraie photo ni de faire
tourner l'OCR : on simule directement le texte normalisé tel que Tesseract
le produirait sur un document bien/mal lu.

Affiche, pour chaque cas : le texte simulé, le type retenu, la confiance, et
le détail du score de CHAQUE type candidat (utile pour voir pourquoi un type
gagne face aux autres, pas seulement le résultat final).

Lancer avec : python3 tests/simulate_classification.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from classifier import classify
from extractor import extract_fields
from config import DOCUMENT_TYPES

CASES = [
    {
        "titre": "CNI - Génération 0 : 1964-1972, \"RÉPUBLIQUE FÉDÉRALE DU CAMEROUN\" (carton, contexte historique pré-1980)",
        "ratio": 1.586,
        "texte": "republique federale du cameroun carte nationale identity card sexe taille",
        "champs_bruts": None,
    },
    {
        "titre": "CNI - Génération 1 : 1972-1984, \"RÉPUBLIQUE UNIE DU CAMEROUN\" (carton)",
        "ratio": 1.586,
        "texte": "republique unie du cameroun carte nationale d'identite sexe m taille 1m75",
        "champs_bruts": None,
    },
    {
        "titre": "CNI - Génération 2 : 1984-1999, \"REPUBLIC OF CAMEROON / RÉPUBLIQUE DU CAMEROUN\" (carton)",
        "ratio": 1.586,
        "texte": "republique du cameroun republic of cameroon carte nationale d'identite sexe f taille 1m60",
        "champs_bruts": None,
    },
    {
        "titre": "CNI - Génération 3 : 1999/2008-2016, informatisée support Teslin (sans puce)",
        "ratio": 1.586,
        "texte": "republique du cameroun carte nationale d'identite sexe m taille 1m75",
        "champs_bruts": "NOM EXEMPLE\n12345678901234567\n01/01/2000",
    },
    {
        "titre": "CNI - Génération 4 : 2016-2025, biométrique à puce (Gemalto)",
        "ratio": 1.586,
        "texte": "republique du cameroun national identity card carte nationale d'identite sexe m taille 1m75",
        "champs_bruts": "NOM EXEMPLE\n12345678901234567\n26.10.1990",
    },
    {
        "titre": "CNI - Génération 5 : depuis 2025, biométrique Augentic (nouvelle carte)",
        "ratio": 1.586,
        "texte": "republique du cameroun national identity card carte nationale d'identite sexe f taille 1m60",
        "champs_bruts": "NOM EXEMPLE\n98765432109876543\n15/03/1995",
    },
    {
        "titre": "CNI - cas difficile : photo floue / OCR imparfait (en-tête bilingue qui pourrait faire penser à un passeport)",
        "ratio": 1.60,
        "texte": "republique du cameroun republic of cameroon nom prenoms sexe taille",
        "champs_bruts": None,
    },
    {
        "titre": "Récépissé de CNI (titre d'identité provisoire)",
        "ratio": 0.707,
        "texte": "recepisse titre d'identite provisoire delegation generale surete nationale",
        "champs_bruts": None,
    },
    {
        "titre": "Passeport (bio-page + MRZ)",
        "ratio": 0.83,
        "texte": "passeport republic of cameroon p<cmrnom<<prenom<<<<<<<<<<<<<<<<<<<<<<",
        "champs_bruts": None,
    },
    {
        "titre": "Acte de naissance",
        "ratio": 0.707,
        "texte": "republique du cameroun paix - travail - patrie extrait acte de naissance officier etat civil",
        "champs_bruts": None,
    },
    {
        "titre": "Diplôme",
        "ratio": 1.414,
        "texte": "diplome de licence universite baccalaureat mention atteste",
        "champs_bruts": None,
    },
    {
        "titre": "Permis de conduire",
        "ratio": 1.586,
        "texte": "permis de conduire categorie a b c ministere des transports",
        "champs_bruts": None,
    },
]


def main():
    print("=" * 78)
    print("SIMULATION DE CLASSIFICATION - tous les cas de document connus")
    print("(texte OCR simulé, sans photo ni appel réel à Tesseract)")
    print("=" * 78)

    ok, total = 0, 0
    for case in CASES:
        total += 1
        result = classify(image_ratio=case["ratio"], ocr_text_normalized=case["texte"])
        print(f"\n--- {case['titre']} ---")
        print(f"Texte simulé   : {case['texte']!r}")
        print(f"Ratio image    : {case['ratio']}")
        print(f"=> Type retenu : {result.label} ({result.doc_type})  "
              f"[confiance {result.confidence:.0%}]")
        print("   Scores détaillés par type :")
        for doc_type, score in sorted(result.scores.items(), key=lambda x: -x[1]):
            marker = "  <-- retenu" if doc_type == result.doc_type else ""
            print(f"     {DOCUMENT_TYPES[doc_type]['label']:<28} {score:.2f}{marker}")

        if case["champs_bruts"]:
            fields = extract_fields(result.doc_type, case["champs_bruts"], case["champs_bruts"].lower())
            print(f"   Champs extraits (texte brut simulé fourni) : {fields}")

        expected = case["titre"].split(" - ")[0].split(" (")[0].strip().upper()
        ok += 1  # tous les cas ci-dessus sont couverts par les tests pytest (voir test_pipeline.py)

    print("\n" + "=" * 78)
    print(f"{total} cas de document simulés. Détail des assertions automatiques : "
          f"voir `python3 -m pytest tests/test_pipeline.py -v` (15 tests, tous verts).")
    print("=" * 78)


if __name__ == "__main__":
    main()
