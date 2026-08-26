"""
Tests unitaires du prétraitement (preprocessing.py) — en particulier la
correction d'orientation, ajoutée après qu'un vrai récépissé/CNI envoyé par
un utilisateur ait donné une lecture OCR totalement incompréhensible ("des
mots sans sens") : la photo avait été prise avec la carte tournée à 90°, et
rien dans le pipeline ne corrigeait ce cas (seul un redressement fin de
quelques degrés était géré).

Lancer avec : python -m pytest tests/test_preprocessing.py -v
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cv2
from PIL import Image, ImageDraw, ImageFont

from preprocessing import _correct_orientation, load_and_clean


def _font(size=28):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _make_cni_like_image():
    """Gabarit texte "CNI" en paysage (même principe que
    tests/generate_sample_images.py), assez de texte pour que la correction
    d'orientation ait matière à travailler."""
    img = Image.new("RGB", (950, 600), "white")
    draw = ImageDraw.Draw(img)
    lines = [
        "REPUBLIQUE DU CAMEROUN",
        "CARTE NATIONALE D'IDENTITE",
        "NOM EXEMPLE PRENOM EXEMPLE",
        "Sexe: M   Taille: 1m75",
        "Ne le 01/01/2000 a Yaounde",
        "Expire le 01/01/2030",
    ]
    y = 30
    for line in lines:
        draw.text((30, y), line, fill="black", font=_font(30))
        y += 70
    return img


def test_correct_orientation_leaves_upright_image_unchanged():
    img = _make_cni_like_image()
    import numpy as np

    bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    corrected = _correct_orientation(bgr)
    # Déjà à l'endroit : la forme (paysage) ne doit pas changer.
    assert corrected.shape == bgr.shape


def test_correct_orientation_fixes_90_degree_rotation():
    import numpy as np

    img = _make_cni_like_image()
    bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    rotated = cv2.rotate(bgr, cv2.ROTATE_90_CLOCKWISE)  # simule une photo prise "de travers"
    assert rotated.shape[0] > rotated.shape[1]  # devenu portrait

    corrected = _correct_orientation(rotated)
    # Redevenu paysage (comme l'original) : la rotation a bien été détectée et corrigée.
    assert corrected.shape[1] > corrected.shape[0]


def test_correct_orientation_fixes_180_degree_rotation():
    import numpy as np

    img = _make_cni_like_image()
    bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    rotated = cv2.rotate(bgr, cv2.ROTATE_180)

    corrected = _correct_orientation(rotated)
    assert corrected.shape == bgr.shape


def test_load_and_clean_corrects_rotated_document_end_to_end():
    """Bout en bout : une image de document tournée à 90° et enregistrée sur
    disque doit ressortir de load_and_clean dans le bon sens."""
    import numpy as np

    img = _make_cni_like_image()
    bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    rotated = cv2.rotate(bgr, cv2.ROTATE_90_CLOCKWISE)

    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        cv2.imwrite(path, rotated)
        corrected, _gray = load_and_clean(path)
        assert corrected.shape[1] > corrected.shape[0]  # de nouveau en paysage
    finally:
        os.unlink(path)


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
