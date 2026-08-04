"""
Extraction des champs (nom, numéro, dates...) à partir du texte OCR brut,
selon le type de document identifié par le classifieur.
"""

import re
import unicodedata
from config import NIU_CNI_REGEX, RECEPISSE_REGEX, DATE_REGEX


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _find_dates(text: str):
    return [f"{d}/{m}/{y}" for d, m, y in re.findall(DATE_REGEX, text)]


def _find_niu(text: str):
    match = re.search(NIU_CNI_REGEX, text)
    return match.group(0) if match else None


def _find_recepisse_number(text: str):
    match = re.search(RECEPISSE_REGEX, text.upper())
    return match.group(0) if match else None


def _is_mrz_like(line: str) -> bool:
    """Détecte une ligne de zone MRZ de façon tolérante à l'OCR.

    On ne peut pas exiger le préfixe exact "P<CMR" : l'OCR lit très souvent
    le caractère '<' comme autre chose (O, 0, K...), mais il en préserve
    généralement AU MOINS quelques-uns. On exige donc la présence d'au moins
    un '<' (signal quasi exclusif à la MRZ dans un document français/anglais)
    combinée à une ligne longue et majoritairement alphanumérique — ça évite
    de confondre une ligne de titre ordinaire (aucun '<') avec une ligne MRZ."""
    compact = line.replace(" ", "")
    if len(compact) < 20 or compact.count("<") == 0:
        return False
    allowed = sum(1 for c in compact if c.isalnum() or c == "<")
    return (allowed / len(compact)) > 0.85


def _find_mrz_lines(raw_text: str):
    lines = [l.strip() for l in raw_text.upper().splitlines() if l.strip()]
    return [l for l in lines if _is_mrz_like(l)]


# Mots-clés (déjà sans accents, en minuscules) qui précèdent le nom/prénom
# sur certains documents où ils sont imprimés sur des lignes séparées
# (typiquement la page biodonnées du passeport).
_SURNAME_LABELS = ["nom", "surname"]
_GIVENNAME_LABELS = ["prenom", "given name", "given names"]


def _find_label_value(raw_text: str, labels: list):
    """Cherche une ligne-étiquette (ex. "1. Nom / Surname") et retourne la
    valeur associée : la ligne suivante non vide.

    Une ligne n'est considérée comme étiquette que si elle a la forme typique
    des champs bilingues des documents officiels camerounais : numérotée
    ("1. Nom...") ou bilingue ("Nom / Surname"). Ça évite de confondre une
    ligne de VALEUR qui contiendrait déjà le mot "nom" (ex. une ligne "NOM
    EXEMPLE" sur une carte au format différent) avec une étiquette."""
    lines = raw_text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        norm = _strip_accents(stripped).lower()
        if not any(label in norm for label in labels):
            continue
        looks_like_label = bool(re.match(r"^\d{1,2}[.)]", stripped)) or "/" in stripped
        if not looks_like_label:
            continue
        for j in range(i + 1, min(i + 3, len(lines))):
            candidate = lines[j].strip()
            if candidate and not _is_mrz_like(candidate) and len(candidate) >= 2:
                return candidate
    return None


# Termes institutionnels à écarter des candidats "nom" : ce sont des en-têtes
# administratifs, pas des noms de personnes.
_NAME_BLACKLIST_TOKENS = {
    "republique", "cameroun", "republic", "cameroon", "carte", "nationale",
    "identite", "identity", "passeport", "passport", "permis", "conduire",
    "ministere", "transports", "extrait", "acte", "naissance", "diplome",
    "recepisse", "delegation", "generale", "surete", "paix", "travail", "patrie",
    "etat", "civil", "officier", "sexe", "taille", "categorie", "delivre",
}


def _guess_name(raw_text: str):
    """Heuristique simple : cherche une ligne en MAJUSCULES d'au moins 2 mots
    qui ressemble à un nom de personne plutôt qu'à un en-tête administratif
    (les noms sont généralement imprimés en capitales sur les documents officiels)."""
    for line in raw_text.splitlines():
        line = line.strip()
        if len(line) < 4:
            continue
        if _is_mrz_like(line):
            continue  # ligne de code MRZ, pas un nom
        words = line.split()
        if len(words) < 2 or line != line.upper() or line.isalpha():
            continue
        letters_only = "".join(c for c in line if c.isalpha())
        if not letters_only or letters_only != letters_only.upper() or len(letters_only) < 4:
            continue

        line_tokens = {_strip_accents(w).lower().strip(".,:;") for w in words}
        if line_tokens & _NAME_BLACKLIST_TOKENS:
            continue  # en-tête administratif, pas un nom

        return line
    return None


def extract_fields(doc_type: str, raw_text: str, normalized_text: str) -> dict:
    dates = _find_dates(raw_text)
    fields = {"type_document": doc_type}

    if doc_type == "CNI":
        fields["nom"] = _guess_name(raw_text)
        fields["numero"] = _find_niu(raw_text)
        fields["date_naissance"] = dates[0] if len(dates) > 0 else None
        fields["date_expiration"] = dates[-1] if len(dates) > 1 else None

    elif doc_type == "RECEPISSE":
        fields["nom"] = _guess_name(raw_text)
        fields["numero_recepisse"] = _find_recepisse_number(raw_text)
        fields["date_delivrance"] = dates[0] if dates else None

    elif doc_type == "PASSEPORT":
        # Sur la page biodonnées, nom et prénom sont souvent sur deux lignes
        # séparées, précédées de leurs étiquettes ("1. Nom/Surname", puis
        # "2. Prénom/s Given name/s") — on tente d'abord cette approche,
        # plus fiable ici que l'heuristique générique à une seule ligne.
        surname = _find_label_value(raw_text, _SURNAME_LABELS)
        given_name = _find_label_value(raw_text, _GIVENNAME_LABELS)
        combined = " ".join(x for x in [surname, given_name] if x)
        fields["nom"] = combined if combined else _guess_name(raw_text)
        fields["date_naissance"] = dates[0] if len(dates) > 0 else None
        fields["date_expiration"] = dates[-1] if len(dates) > 1 else None
        mrz_lines = _find_mrz_lines(raw_text)
        fields["mrz"] = " ".join(mrz_lines) if mrz_lines else None

    elif doc_type == "ACTE_NAISSANCE":
        fields["nom"] = _guess_name(raw_text)
        fields["date_naissance"] = dates[0] if dates else None
        lieu_match = re.search(r"(?:a|à)\s+([A-ZÀ-Ü][a-zà-ü\-]+)", raw_text)
        fields["lieu_naissance"] = lieu_match.group(1) if lieu_match else None

    elif doc_type == "DIPLOME":
        fields["nom"] = _guess_name(raw_text)
        fields["date_delivrance"] = dates[0] if dates else None
        matricule_match = re.search(r"matricule\s*[:\-]?\s*([A-Z0-9\-]+)", normalized_text)
        fields["numero_matricule"] = matricule_match.group(1).upper() if matricule_match else None

    elif doc_type == "PERMIS":
        fields["nom"] = _guess_name(raw_text)
        fields["date_naissance"] = dates[0] if len(dates) > 0 else None
        fields["date_delivrance"] = dates[-1] if len(dates) > 1 else None
        categories = re.findall(r"\b[ABCDE]1?\b", raw_text.upper())
        fields["categories"] = sorted(set(categories)) if categories else None

    else:
        fields["nom"] = _guess_name(raw_text)
        fields["dates_detectees"] = dates

    return fields