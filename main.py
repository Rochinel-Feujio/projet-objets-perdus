"""
Point d'entrée du pipeline complet :
photo (ou PDF scanné) -> prétraitement -> OCR -> classification -> extraction
-> validation -> enregistrement

Usage :
    python main.py chemin/vers/photo.jpg
    python main.py chemin/vers/document.pdf
"""

import os
import sys
import json

from preprocessing import load_and_clean, get_aspect_ratio, is_blurry
from ocr import extract_text, normalize_text
from classifier import classify
from extractor import extract_fields
from validator import validate
from storage import save_document
from zones import read_zones
from pdf_input import is_pdf, pdf_first_page_to_image


def analyze_document(image_path: str, debug: bool = False) -> dict:
    """Exécute tout le pipeline de détection (prétraitement -> OCR ->
    classification -> extraction -> validation) SANS rien enregistrer en
    base. Utile quand on veut juste lire un document (ex. pré-remplir un
    formulaire de déclaration de perte à partir d'une ancienne photo) sans
    créer une entrée dans la table `documents` (réservée aux documents
    effectivement retrouvés).

    Accepte aussi bien une image (JPG/PNG) qu'un PDF : dans ce dernier cas,
    la première page est automatiquement convertie en image avant analyse
    (voir pdf_input.py) — un document scanné en PDF plutôt que photographié
    est traité exactement de la même façon."""
    working_path = image_path
    pdf_page_count = None
    if is_pdf(image_path):
        working_path, pdf_page_count = pdf_first_page_to_image(image_path)

    try:
        # 1. Prétraitement : détection du contour + correction de perspective
        # (ou redressement simple en repli), amélioration du contraste.
        image, _gray = load_and_clean(working_path)
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
        if pdf_page_count and pdf_page_count > 1:
            alerts.insert(
                0,
                f"Ce PDF contient {pdf_page_count} pages : seule la première a été analysée "
                f"(les documents administratifs tiennent généralement sur une seule page).",
            )

        return {
            "type_document": result.label,
            "confidence": result.confidence,
            "scores_detail": result.scores,
            "champs": fields,
            "alertes": alerts,
            "nettete": round(sharpness, 1),
            "floue": blurry,
        }
    finally:
        # Le fichier image converti depuis le PDF n'est qu'un intermédiaire
        # temporaire — il n'a pas vocation à rester sur disque.
        if pdf_page_count is not None and working_path != image_path:
            try:
                os.unlink(working_path)
            except OSError:
                pass


def process_document(
    image_path: str,
    debug: bool = False,
    user_id: int = None,
    finder_contact: str = None,
) -> dict:
    """analyze_document() puis enregistrement en base (table `documents`,
    réservée aux documents effectivement retrouvés). `user_id` identifie la
    personne qui a retrouvé le document (si connectée) et `finder_contact`
    est le moyen de la recontacter, affiché sur l'écran de détail via
    "voir les coordonnées"."""
    analysis = analyze_document(image_path, debug=debug)

    doc_id = save_document(
        analysis["champs"],
        analysis["confidence"],
        analysis["alertes"],
        image_path,
        user_id=user_id,
        finder_contact=finder_contact,
    )

    return {"id": doc_id, **analysis}


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
        print("        python main.py chemin/vers/document.pdf [--debug]")
        sys.exit(1)

    output = process_document(args[0], debug=debug_mode)
    print_result(output)
    print("\n--- JSON structuré ---")
    print(json.dumps(output["champs"], ensure_ascii=False, indent=2))
