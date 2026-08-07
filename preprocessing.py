"""
Prétraitement de l'image : détection du contour du document, correction de
perspective, redressement, amélioration du contraste, réduction du bruit,
détection de flou.
"""

import cv2
import numpy as np


def load_and_clean(image_path: str):
    """Charge une image et applique un nettoyage complet.

    Étapes : détection du contour du document + correction de perspective
    (si un contour net à 4 coins est trouvé), sinon simple redressement de
    l'inclinaison ; puis amélioration du contraste et réduction du bruit.

    Retourne un tuple (image_couleur_corrigee, image_niveaux_de_gris_ameliore).
    """
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Impossible de lire l'image : {image_path}")

    corrected, perspective_applied = _perspective_correct(image)
    if not perspective_applied:
        corrected = _deskew(corrected)

    gray = cv2.cvtColor(corrected, cv2.COLOR_BGR2GRAY)
    gray = cv2.fastNlMeansDenoising(gray, h=10)
    gray = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
    )
    return corrected, gray


# ---------------------------------------------------------------------------
# Correction de perspective : détecte les 4 coins du document dans la photo
# et le "met à plat", comme un scanner. Corrige bien mieux un angle de prise
# de vue qu'un simple redressement de rotation.
# ---------------------------------------------------------------------------

def _order_points(pts: np.ndarray) -> np.ndarray:
    """Ordonne 4 points dans l'ordre : haut-gauche, haut-droite, bas-droite, bas-gauche."""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def _find_document_contour(image):
    """Cherche le plus grand contour à 4 côtés couvrant une portion significative
    de l'image (le document). Retourne None si rien d'assez net n'est trouvé."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 50, 150)
    edged = cv2.dilate(edged, None, iterations=2)
    edged = cv2.erode(edged, None, iterations=1)

    contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    image_area = image.shape[0] * image.shape[1]
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

    for c in contours:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        # On exige un quadrilatère couvrant au moins 20% de l'image : évite de
        # "corriger" la perspective sur un petit détail (logo, reflet...) plutôt
        # que sur le document lui-même.
        if len(approx) == 4 and cv2.contourArea(approx) > 0.20 * image_area:
            return approx.reshape(4, 2)
    return None


def _perspective_correct(image):
    """Tente une correction de perspective complète. Retourne (image, True) si
    appliquée, ou (image_originale, False) si aucun contour fiable n'a été trouvé
    — dans ce cas l'appelant peut se rabattre sur un simple redressement."""
    pts = _find_document_contour(image)
    if pts is None:
        return image, False

    rect = _order_points(pts.astype("float32"))
    (tl, tr, br, bl) = rect

    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    max_width = max(int(width_a), int(width_b))

    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_height = max(int(height_a), int(height_b))

    # Contour trop petit ou dégénéré : pas fiable, on abandonne la correction.
    if max_width < 80 or max_height < 80:
        return image, False

    dst = np.array(
        [[0, 0], [max_width - 1, 0], [max_width - 1, max_height - 1], [0, max_height - 1]],
        dtype="float32",
    )
    matrix = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, matrix, (max_width, max_height))
    return warped, True


def _deskew(image):
    """Redresse légèrement l'image si elle est inclinée (fallback si la
    correction de perspective n'a pas trouvé de contour exploitable)."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=100, minLineLength=100, maxLineGap=10)
    if lines is None:
        return image

    angles = []
    for line in lines:
        # cv2.HoughLinesP renvoie un format (N, 1, 4) sur la plupart des versions
        # d'OpenCV, mais (N, 4) sur certaines — on aplatit pour gérer les deux.
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


# ---------------------------------------------------------------------------
# Détection de flou
# ---------------------------------------------------------------------------

def is_blurry(image, threshold: float = 80.0):
    """Détecte si une image est probablement trop floue pour une lecture OCR
    fiable, via la variance du Laplacien (une image nette a des contours
    marqués donc une variance élevée ; une image floue a des transitions
    douces donc une variance faible).

    Retourne (est_floue: bool, score_de_nettete: float).
    Seuil indicatif : en dessous de ~80-100, la photo est généralement trop
    floue pour une bonne lecture ; au-dessus de ~300, l'image est bien nette.
    Le seuil par défaut reste volontairement prudent (peu de faux positifs)."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    variance = cv2.Laplacian(gray, cv2.CV_64F).var()
    return variance < threshold, float(variance)


def get_aspect_ratio(image) -> float:
    """Retourne largeur / hauteur de l'image (orientation paysage = ratio > 1)."""
    h, w = image.shape[:2]
    return w / h