"""
Point d'entrée du pipeline complet :
photo -> prétraitement -> OCR -> classification -> extraction -> validation -> enregistrement

Usage :
    python main.py chemin/vers/photo.jpg [--debug]
"""

import sys
import json

from preprocessing import load_and_clean, get_aspect_ratio
from ocr import extract_text, extract_text_normalized
from classifier import classify
from extractor import extract_fields
from validator import validate
from storage import save_document


def process_document(image_path: str, debug: bool = False) -> dict:
    image, _gray = load_and_clean(image_path)
    ratio = get_aspect_ratio(image)

    raw_text = extract_text(image_path)
    normalized_text = extract_text_normalized(image_path)

    if debug:
        print("=" * 60)
        print(f"Ratio largeur/hauteur de l'image : {ratio:.2f}")
        print("-" * 60)
        print("Texte brut lu par l'OCR (avant tout traitement) :")
        print("-" * 60)
        print(raw_text if raw_text.strip() else "(rien lu par l'OCR)")
        print("=" * 60)

    result = classify(ratio, normalized_text)

    if debug:
        print(f"Scores de classification : {result.scores}")
        print("=" * 60)

    fields = extract_fields(result.doc_type, raw_text, normalized_text)
    alerts = validate(result.doc_type, fields)
    doc_id = save_document(fields, result.confidence, alerts, image_path)

    return {
        "id": doc_id,
        "type_document": result.label,
        "confidence": result.confidence,
        "scores_detail": result.scores,
        "champs": fields,
        "alertes": alerts,
    }


def print_result(result: dict):
    print(f"Ceci est : {result['type_document']} (confiance : {result['confidence']:.0%})")
    for key, value in result["champs"].items():
        if key == "type_document":
            continue
        print(f"  {key} : {value}")
    if result["alertes"]:
        print("Alertes :")
        for alert in result["alertes"]:
            print(f"  - {alert}")
    else:
        print("Informations enregistrées avec succès.")
    print(f"(id base de données : {result['id']})")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--debug"]
    debug_mode = "--debug" in sys.argv

    if len(args) != 1:
        print("Usage : python main.py chemin/vers/photo.jpg [--debug]")
        sys.exit(1)

    output = process_document(args[0], debug=debug_mode)
    print_result(output)
    print("\n--- JSON structuré ---")
    print(json.dumps(output["champs"], ensure_ascii=False, indent=2))