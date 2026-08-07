"""
Point d'entrée du pipeline complet :
photo -> prétraitement -> OCR -> classification -> extraction -> validation -> enregistrement

Usage :
    python main.py chemin/vers/photo.jpg
"""

import sys
import json

from preprocessing import load_and_clean, get_aspect_ratio, is_blurry
from ocr import extract_text, normalize_text
from classifier import classify
from extractor import extract_fields
from validator import validate
from storage import save_document
from zones import read_zones


def process_document(image_path: str, debug: bool = False) -> dict:
    # 1. Prétraitement : détection du contour + correction de perspective
    # (ou redressement simple en repli), amélioration du contraste.
    image, _gray = load_and_clean(image_path)
    ratio = get_aspect_ratio(image)

    # 2. Détection de flou — sur l'image déjà corrigée.
    blurry, sharpness = is_blurry(image)

    # 3. OCR — directement sur l'image corrigée en mémoire (redressée/recadrée),
    # plus fiable qu'une relecture du fichier original non corrigé. Une seule
    # passe OCR, puis normalisation du même texte (évite de lire deux fois).
    raw_text = extract_text(image)
    normalized_text = normalize_text(raw_text)

    if debug:
        print("=" * 60)
        print(f"Ratio largeur/hauteur de l'image (après correction) : {ratio:.2f}")
        print(f"Netteté (variance Laplacien) : {sharpness:.1f} {'-> FLOUE' if blurry else '-> nette'}")
        print("-" * 60)
        print("Texte brut lu par l'OCR (sur l'image corrigée) :")
        print("-" * 60)
        print(raw_text if raw_text.strip() else "(rien lu par l'OCR)")
        print("=" * 60)

    # 4. Identification du type de document
    result = classify(ratio, normalized_text)

    if debug:
        print(f"Scores de classification : {result.scores}")
        print("=" * 60)

    # 4bis. Lecture par zones : une fois le type de document connu, on relit
    # l'OCR séparément sur chaque zone de champ connue de sa mise en page
    # (nom, prénom, dates...) plutôt que de se fier uniquement au texte
    # global. Fonctionne pour les 6 types de documents (voir zones.py) ; si
    # aucune zone n'est définie ou que la lecture échoue, on obtient un dict
    # vide et extract_fields se rabat automatiquement sur l'ancienne méthode.
    zone_texts = read_zones(image, result.doc_type)

    if debug:
        print("Lecture par zones :")
        if zone_texts:
            for field_name, text in zone_texts.items():
                print(f"  {field_name} : {text!r}")
        else:
            print("  (aucune zone exploitable pour ce type de document)")
        print("=" * 60)

    # 5. Extraction des champs
    fields = extract_fields(result.doc_type, raw_text, normalized_text, zone_texts)

    # 6. Validation
    alerts = validate(result.doc_type, fields)
    if blurry:
        alerts.insert(
            0,
            f"Photo probablement trop floue pour une lecture fiable "
            f"(netteté : {sharpness:.0f}/80 recommandé) — reprends la photo si possible.",
        )

    # 7. Enregistrement
    doc_id = save_document(fields, result.confidence, alerts, image_path)

    return {
        "id": doc_id,
        "type_document": result.label,
        "confidence": result.confidence,
        "scores_detail": result.scores,
        "champs": fields,
        "alertes": alerts,
        "nettete": round(sharpness, 1),
        "floue": blurry,
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