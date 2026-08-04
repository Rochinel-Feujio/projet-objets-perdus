"""
Prétraitement de l'image : chargement, correction d'orientation,
amélioration du contraste, réduction du bruit.
"""

import cv2
import numpy as np


def load_and_clean(image_path: str):
    """Charge une image et applique un nettoyage de base.

    Retourne un tuple (image_couleur, image_niveaux_de_gris_ameliore).
    """
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Impossible de lire l'image : {image_path}")

    image = _deskew(image)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.fastNlMeansDenoising(gray, h=10)
    gray = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
    )
    return image, gray


def _deskew(image):
    """Redresse légèrement l'image si elle est inclinée (détection de contours)."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=100, minLineLength=100, maxLineGap=10)
    if lines is None:
        return image

    angles = []
    for line in lines:
        x1, y1, x2, y2 = np.asarray(line).reshape(-1)[:4]
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        if -45 < angle < 45:
            angles.append(angle)

    if not angles:
        return image

    median_angle = float(np.median(angles))
    if abs(median_angle) < 0.5:
        return image  # déjà droit

    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    rotation_matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    return cv2.warpAffine(image, rotation_matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def get_aspect_ratio(image) -> float:
    """Retourne largeur / hauteur de l'image (orientation paysage = ratio > 1)."""
    h, w = image.shape[:2]
    return w / h
