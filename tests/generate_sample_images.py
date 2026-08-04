"""
Génère des images de test synthétiques (texte imprimé sur fond blanc, aux bonnes
proportions) pour valider le pipeline de bout en bout SANS vraies photos de documents.
Ce ne sont PAS des CNI réalistes visuellement — seulement des gabarits texte utiles
pour tester OCR + classification + extraction + validation.
"""

import os
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = os.path.join(os.path.dirname(__file__), "sample_images")
os.makedirs(OUT_DIR, exist_ok=True)


def _font(size=28):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default()


def make_image(filename, width, height, lines):
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    y = 30
    for line in lines:
        draw.text((30, y), line, fill="black", font=_font(26))
        y += 40
    path = os.path.join(OUT_DIR, filename)
    img.save(path)
    return path


def main():
    # Carte CNI (ratio ~1.586, ex. 950x600)
    make_image("cni_sample.png", 950, 600, [
        "REPUBLIQUE DU CAMEROUN",
        "CARTE NATIONALE D'IDENTITE",
        "NOM EXEMPLE",
        "Sexe: M   Taille: 1m75",
        "12345678901234567",
        "Ne le 01/01/2000",
        "Expire le 01/01/2030",
    ])

    # Permis (même ratio que CNI mais tableau de categories)
    make_image("permis_sample.png", 950, 600, [
        "PERMIS DE CONDUIRE",
        "MINISTERE DES TRANSPORTS",
        "NOM EXEMPLE",
        "Categorie A B C",
        "Ne le 05/05/1995",
        "Delivre le 10/10/2020",
    ])

    # Passeport (ratio portrait ~0.83, page biodonnees avec MRZ)
    make_image("passeport_sample.png", 700, 850, [
        "PASSEPORT",
        "REPUBLIC OF CAMEROON",
        "NOM EXEMPLE",
        "Ne le 12/12/1990",
        "Expire le 12/12/2030",
        "P<CMRNOM<<PRENOM<<<<<<<<<<<<<<<<<<<<<<<<<<<<",
        "1234567890CMR9012120M3012120<<<<<<<<<<<<<<02",
    ])

    # Acte de naissance (A4 portrait ~0.707)
    make_image("acte_naissance_sample.png", 700, 990, [
        "REPUBLIQUE DU CAMEROUN",
        "PAIX - TRAVAIL - PATRIE",
        "EXTRAIT D'ACTE DE NAISSANCE",
        "NOM EXEMPLE",
        "Ne le 03/03/2015 a Yaounde",
        "Officier d'etat civil",
    ])

    print(f"Images générées dans : {OUT_DIR}")


if __name__ == "__main__":
    main()
