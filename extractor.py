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


def _zone_line(zone_texts: dict, key: str):
    """Première ligne exploitable du texte lu dans une zone donnée, ou None
    si la zone n'a rien donné (zone absente pour ce type de document, ou OCR
    n'ayant rien reconnu dedans)."""
    if not zone_texts:
        return None
    raw = zone_texts.get(key)
    if not raw:
        return None
    for line in raw.splitlines():
        line = line.strip()
        if line:
            return line
    return None


def _looks_like_name_value(text: str) -> bool:
    """Filtre de plausibilité pour une valeur de zone censée contenir un nom
    ou un prénom. Protège contre un mauvais recadrage de zone (zone estimée
    non calibrée, ou photo au cadrage inhabituel) qui donnerait un fragment
    de texte sans rapport (ex. un bout de la case "Taille" voisine) plutôt
    que de risquer d'écraser une extraction correcte par du bruit."""
    if not text or len(text) < 3:
        return False
    if "<" in text or _is_mrz_like(text):
        return False  # zone mal cadrée ayant capté (une partie de) la ligne MRZ plutôt que le nom
    letters = sum(1 for c in text if c.isalpha())
    digits = sum(1 for c in text if c.isdigit())
    if letters < 3 or digits > letters:
        return False
    return True


def _zone_name(zone_texts: dict, key: str):
    """Comme _zone_line, mais uniquement pour des champs nom/prénom : la
    valeur doit ressembler à un nom pour être retenue, sinon on laisse
    l'appelant se rabattre sur l'heuristique globale."""
    value = _zone_line(zone_texts, key)
    return value if value and _looks_like_name_value(value) else None


def _parse_mrz_name(mrz_line: str):
    """Repère nom et prénom dans une ligne 1 de MRZ (format "P<CMRNOM<<PRENOM
    <<<<...<"), même très bruitée par l'OCR.

    Principe : après le code pays (CMR — toléré CHR/CMP/CNR... au cas où l'OCR
    déforme une lettre), le premier "mot" d'au moins 4 lettres est le nom, le
    second est le prénom. On ne cherche pas les caractères '<' exacts (l'OCR
    les lit très souvent comme autre chose : K, O, des espaces...) — on se
    base uniquement sur les suites de lettres, qui elles restent fiables."""
    tokens = re.findall(r"[A-Z]{4,}", mrz_line.upper())
    for i, tok in enumerate(tokens):
        match = re.search(r"C[MHN][RP]", tok)
        if not match:
            continue
        surname = tok[match.end():]
        given_name = tokens[i + 1] if i + 1 < len(tokens) else None
        if surname:
            return surname, given_name
    return None, None


def _parse_mrz_passport_number(mrz_text: str):
    """Le numéro de passeport a la forme 1-2 lettres + 6-8 chiffres (ex.
    "AB156755"), au tout début de la 2e ligne de la MRZ. On cherche ce motif
    n'importe où dans le texte MRZ plutôt qu'en imposant "en tout début de
    ligne" : l'OCR ne préserve pas toujours proprement le retour à la ligne
    entre les deux lignes de la MRZ (parfois collées, séparées par un simple
    espace) — le motif lettres+chiffres reste lui identifiable dans tous les cas."""
    match = re.search(r"\b[A-Z]{1,2}[0-9]{6,8}\b", mrz_text.upper())
    return match.group(0) if match else None


def _extract_from_mrz(mrz_lines: list):
    """Dernier recours pour nom/prénom/numéro sur un passeport : si ni la
    lecture par zones ni les étiquettes bilingues n'ont rien donné d'exploitable
    en haut de page, on les retrouve dans la MRZ — conçue justement pour rester
    lisible même sur un OCR imparfait. On travaille sur le texte MRZ fusionné
    (pas ligne par ligne) car les deux lignes de la MRZ ne sont pas toujours
    proprement séparées par l'OCR."""
    full_text = " ".join(mrz_lines)
    surname, given_name = _parse_mrz_name(full_text)
    passport_number = _parse_mrz_passport_number(full_text)
    return surname, given_name, passport_number


def _zone_date(zone_texts: dict, key: str):
    """Cherche une date dans le texte d'une zone précise — plus fiable que de
    prendre la Nème date trouvée dans tout le texte de l'image, puisque la
    zone ne contient (en principe) que ce champ-là."""
    if not zone_texts:
        return None
    raw = zone_texts.get(key)
    if not raw:
        return None
    found = _find_dates(raw)
    return found[0] if found else None


def extract_fields(doc_type: str, raw_text: str, normalized_text: str, zone_texts: dict = None) -> dict:
    """Extrait les champs d'un document.

    `zone_texts` (optionnel) : résultat de zones.read_zones(image, doc_type) —
    texte OCR lu spécifiquement dans chaque zone connue de la mise en page de
    ce type de document. Utilisé en priorité quand disponible et exploitable ;
    on se rabat sinon sur les heuristiques appliquées au texte global (lecture
    OCR de l'image entière), qui restent le comportement par défaut si aucune
    zone n'est définie pour ce type ou si la lecture de zone est vide."""
    zone_texts = zone_texts or {}
    dates = _find_dates(raw_text)
    fields = {"type_document": doc_type}

    if doc_type == "CNI":
        nom_zone = _zone_name(zone_texts, "nom")
        prenom_zone = _zone_name(zone_texts, "prenom")
        combined = " ".join(x for x in [nom_zone, prenom_zone] if x)
        fields["nom"] = combined if combined else _guess_name(raw_text)
        fields["numero"] = _find_niu(raw_text)  # NIU au verso : pas de zone dédiée sur le recto
        fields["date_naissance"] = _zone_date(zone_texts, "date_naissance") or (dates[0] if dates else None)
        fields["date_expiration"] = dates[-1] if len(dates) > 1 else None

    elif doc_type == "RECEPISSE":
        nom_zone = _zone_name(zone_texts, "nom")
        fields["nom"] = nom_zone or _guess_name(raw_text)
        fields["numero_recepisse"] = _find_recepisse_number(raw_text)
        fields["date_delivrance"] = dates[0] if dates else None

    elif doc_type == "PASSEPORT":
        mrz_lines = _find_mrz_lines(zone_texts.get("mrz", "")) or _find_mrz_lines(raw_text)
        mrz_surname, mrz_given_name, mrz_passport_number = (
            _extract_from_mrz(mrz_lines) if mrz_lines else (None, None, None)
        )

        nom_zone = _zone_name(zone_texts, "nom")
        prenom_zone = _zone_name(zone_texts, "prenom")
        combined = " ".join(x for x in [nom_zone, prenom_zone] if x)
        if not combined:
            # Repli 1 : étiquettes bilingues ("1. Nom/Surname" puis valeur sur
            # la ligne suivante) recherchées dans le texte global.
            surname = _find_label_value(raw_text, _SURNAME_LABELS)
            given_name = _find_label_value(raw_text, _GIVENNAME_LABELS)
            combined = " ".join(x for x in [surname, given_name] if x)
        if not combined and (mrz_surname or mrz_given_name):
            # Repli 2 : nom/prénom pas identifiés en haut de page -> on les
            # retrouve dans la MRZ (voir _extract_from_mrz).
            combined = " ".join(x for x in [mrz_surname, mrz_given_name] if x)
        fields["nom"] = combined if combined else _guess_name(raw_text)
        fields["numero"] = mrz_passport_number
        fields["date_naissance"] = _zone_date(zone_texts, "date_naissance") or (dates[0] if dates else None)
        fields["date_expiration"] = _zone_date(zone_texts, "date_expiration") or (dates[-1] if len(dates) > 1 else None)
        fields["mrz"] = " ".join(mrz_lines) if mrz_lines else None

    elif doc_type == "ACTE_NAISSANCE":
        nom_zone = _zone_name(zone_texts, "nom")
        fields["nom"] = nom_zone or _guess_name(raw_text)
        fields["date_naissance"] = _zone_date(zone_texts, "date_naissance") or (dates[0] if dates else None)
        lieu_match = re.search(r"(?:a|à)\s+([A-ZÀ-Ü][a-zà-ü\-]+)", raw_text)
        fields["lieu_naissance"] = lieu_match.group(1) if lieu_match else None

    elif doc_type == "DIPLOME":
        nom_zone = _zone_name(zone_texts, "nom")
        fields["nom"] = nom_zone or _guess_name(raw_text)
        fields["date_delivrance"] = dates[0] if dates else None
        matricule_match = re.search(r"matricule\s*[:\-]?\s*([A-Z0-9\-]+)", normalized_text)
        fields["numero_matricule"] = matricule_match.group(1).upper() if matricule_match else None

    elif doc_type == "PERMIS":
        nom_zone = _zone_name(zone_texts, "nom")
        fields["nom"] = nom_zone or _guess_name(raw_text)
        fields["date_naissance"] = _zone_date(zone_texts, "date_naissance") or (dates[0] if dates else None)
        fields["date_delivrance"] = dates[-1] if len(dates) > 1 else None
        categories_source = zone_texts.get("categories", raw_text)
        categories = re.findall(r"\b[ABCDE]1?\b", categories_source.upper())
        fields["categories"] = sorted(set(categories)) if categories else None

    else:
        fields["nom"] = _guess_name(raw_text)
        fields["dates_detectees"] = dates

    return fields