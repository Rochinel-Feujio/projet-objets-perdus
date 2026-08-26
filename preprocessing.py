"""
Prétraitement de l'image : détection du contour du document, correction de
perspective, redressement, amélioration du contraste, réduction du bruit,
détection de flou.
"""

import cv2
import numpy as np
import pytesseract
from PIL import Image as _PILImage


def load_and_clean(image_path: str):
    """Charge une image et applique un nettoyage complet.

    Étapes : correction d'une éventuelle rotation franche à 90/180/270°
    (photo prise "de travers") ; détection du contour du document +
    correction de perspective (si un contour net à 4 coins est trouvé),
    sinon simple redressement de l'inclinaison ; puis amélioration du
    contraste et réduction du bruit.

    Retourne un tuple (image_couleur_corrigee, image_niveaux_de_gris_ameliore).
    """
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Impossible de lire l'image : {image_path}")

    image = _correct_orientation(image)

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
# Correction d'orientation : détecte si la photo a été prise "de travers"
# (carte tenue en paysage au lieu de portrait, ou à l'envers) et la remet
# dans le bon sens AVANT tout le reste. Sans cette étape, un document
# correctement net peut donner un texte totalement incompréhensible en OCR
# (lettres mélangées sans aucun sens) simplement parce qu'il est tourné à
# 90° — un cas rencontré concrètement avec de vrais récépissés/CNI envoyés
# en PDF par les utilisateurs.
# ---------------------------------------------------------------------------

_ORIENTATION_ROTATION_CODES = {
    0: None,
    90: cv2.ROTATE_90_CLOCKWISE,
    180: cv2.ROTATE_180,
    270: cv2.ROTATE_90_COUNTERCLOCKWISE,
}


def _rotate_by(image, angle: int):
    code = _ORIENTATION_ROTATION_CODES[angle]
    return image if code is None else cv2.rotate(image, code)


def _orientation_score(image) -> int:
    """Score une orientation candidate : plus il y a de mots plausibles
    (>= 3 lettres, confiance Tesseract > 40) reconnus par une lecture OCR
    rapide, plus le score est élevé. Une orientation correcte donne presque
    toujours un score nettement supérieur aux 3 autres, car du texte à
    l'envers ou tourné à 90° ne produit quasiment aucun mot reconnaissable.

    On a délibérément écarté la détection d'orientation native de Tesseract
    (`image_to_osd`) : testée sur de vraies photos de documents (peu de
    texte, beaucoup de motifs/logos), elle s'est révélée peu fiable et
    incohérente d'un appel à l'autre (résultat différent selon la seule
    résolution de l'image, avec une confiance systématiquement très
    faible). Compter les mots effectivement reconnus par un essai d'OCR
    réel dans chaque orientation s'est montré beaucoup plus robuste en
    pratique, aussi bien sur des images de test synthétiques que sur de
    vraies photos de CNI/récépissés."""
    try:
        pil_image = _PILImage.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        data = pytesseract.image_to_data(
            pil_image, lang="fra+eng", config="--psm 6", output_type=pytesseract.Output.DICT
        )
    except Exception:
        return 0

    score = 0
    for text, conf in zip(data.get("text", []), data.get("conf", [])):
        text = text.strip()
        try:
            conf = int(conf)
        except (TypeError, ValueError):
            continue
        if conf > 40 and len(text) >= 3 and text.isalpha():
            score += conf
    return score


def _correct_orientation(image):
    """Détecte et corrige une rotation franche à 90/180/270°. Se limite
    volontairement à ces 4 orientations : le redressement fin de quelques
    degrés reste géré séparément par `_deskew`, plus bas.

    Teste rapidement les 4 orientations sur une copie réduite de l'image
    (pour rester rapide) et garde celle qui produit le plus de texte
    reconnaissable, puis applique cette rotation à l'image en pleine
    résolution. Si aucune orientation ne produit le moindre mot
    reconnaissable (document très flou, endommagé, ou sans texte), on
    renvoie l'image telle quelle plutôt que de tourner au hasard."""
    h, w = image.shape[:2]
    long_side = max(h, w)
    if long_side == 0:
        return image

    scale = min(1.0, 1200 / long_side)
    small = (
        cv2.resize(image, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
        if scale < 1.0
        else image
    )

    scores = {angle: _orientation_score(_rotate_by(small, angle)) for angle in _ORIENTATION_ROTATION_CODES}
    best_angle = max(scores, key=scores.get)
    if scores[best_angle] == 0:
        return image

    return _rotate_by(image, best_angle)


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