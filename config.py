"""
Configuration : définitions des types de documents, mots-clés OCR,
formats de numéros et plages de ratio d'aspect (largeur/hauteur).

Ces critères viennent du document de référence
"Critères de différenciation des documents administratifs camerounais".
"""

# Ratio = largeur / hauteur de l'image (après redressement).
# Une carte ID-1 (CNI, permis) ≈ 1.586. Une feuille A4 portrait ≈ 0.707,
# en paysage ≈ 1.414. Page de passeport ≈ 0.83 (portrait).
CARD_RATIO_RANGE = (1.35, 1.80)      # carte type CNI / permis
A4_PORTRAIT_RATIO_RANGE = (0.60, 0.80)
A4_LANDSCAPE_RATIO_RANGE = (1.25, 1.65)  # diplômes souvent en paysage -> chevauche la plage carte, départagé par OCR
PASSPORT_PAGE_RATIO_RANGE = (0.75, 0.95)

DOCUMENT_TYPES = {
    "CNI": {
        "label": "Carte Nationale d'Identité",
        "formats": ["card"],
        "keywords": ["carte nationale", "identite", "republique du cameroun", "sexe", "taille"],
        "exclude_keywords": ["permis", "categorie", "diplome", "acte de naissance"],
    },
    "RECEPISSE": {
        "label": "Récépissé de CNI",
        "formats": ["a4_portrait", "a4_landscape"],
        "keywords": ["recepisse", "titre d'identite provisoire", "delegation generale", "surete nationale"],
        "exclude_keywords": [],
    },
    "PASSEPORT": {
        "label": "Passeport",
        "formats": ["passport_page", "card"],
        # "republic of cameroon" retiré : cet en-tête bilingue figure aussi sur
        # la CNI ("RÉPUBLIQUE DU CAMEROUN / REPUBLIC OF CAMEROON"), donc il ne
        # distingue pas un passeport d'une CNI — au contraire, il faisait
        # basculer à tort des CNI mal lues par l'OCR vers "Passeport" (repéré
        # sur un vrai récépissé/CNI envoyé par un utilisateur). "passeport"/
        # "passport" + la détection MRZ restent des signaux fiables et propres
        # au passeport.
        "keywords": ["passeport", "passport"],
        "mrz_required_or_keyword": True,
        "exclude_keywords": [],
    },
    "ACTE_NAISSANCE": {
        "label": "Acte de naissance",
        "formats": ["a4_portrait"],
        "keywords": ["acte de naissance", "extrait", "etat civil", "paix - travail - patrie", "officier"],
        "exclude_keywords": ["diplome", "permis"],
    },
    "DIPLOME": {
        "label": "Diplôme",
        "formats": ["a4_landscape", "a4_portrait"],
        "keywords": ["diplome", "baccalaureat", "licence", "master", "universite", "atteste"],
        "exclude_keywords": [],
    },
    "PERMIS": {
        "label": "Permis de conduire",
        "formats": ["card"],
        "keywords": ["permis de conduire", "categorie", "ministere des transports"],
        "exclude_keywords": ["carte nationale"],
    },
}

# Champs demandés dans le formulaire de déclaration de perte, par type de
# document — uniquement les champs utiles pour retrouver une correspondance
# avec un document retrouvé (mêmes clés que celles produites par
# extractor.extract_fields(), pour que la comparaison soit directe).
DECLARATION_FIELDS = {
    "CNI": ["nom", "numero", "date_naissance"],
    "RECEPISSE": ["nom", "numero_recepisse"],
    "PASSEPORT": ["nom", "numero"],
    "ACTE_NAISSANCE": ["nom", "date_naissance", "lieu_naissance"],
    "DIPLOME": ["nom", "numero_matricule"],
    "PERMIS": ["nom", "date_naissance"],
}

# Libellés affichés dans le formulaire pour chaque clé de champ.
FIELD_LABELS = {
    "nom": "Nom complet",
    "numero": "Numéro du document",
    "numero_recepisse": "Numéro du récépissé",
    "numero_matricule": "Numéro de matricule",
    "date_naissance": "Date de naissance (jj/mm/aaaa)",
    "lieu_naissance": "Lieu de naissance",
}

# Motif de la zone MRZ (2 lignes, alphabet ICAO restreint, ~44 caractères).
MRZ_LINE_REGEX = r"[A-Z0-9<]{30,44}"

# Validation des numéros connus.
NIU_CNI_REGEX = r"\b\d{17}\b"
RECEPISSE_REGEX = r"\b(AD|CE|ES|EN|NO|SU|LT|OU|NW|SW)[A-Z0-9]{18}\b"
# Accepte "/", "-" ET "." comme séparateur : les vraies CNI camerounaises
# utilisent souvent des dates au format "26.10.1965" (point), pas seulement
# "/" ou "-" — un vrai récépissé/CNI envoyé par un utilisateur avait une date
# de naissance parfaitement lisible par l'OCR ("26.10.1965") mais totalement
# ignorée par l'extraction faute de séparateur reconnu.
DATE_REGEX = r"\b(\d{2})[/\-.](\d{2})[/\-.](\d{4})\b"

DB_PATH = "documents.db"

# --- IA de vision en complément de l'OCR (optionnel — voir ai_vision.py) ---
# On ne sollicite l'IA de vision que quand l'OCR local semble peu fiable
# (confiance de classification sous ce seuil, ou au moins un champ non lu),
# pas systématiquement — ça évite de gaspiller inutilement le quota gratuit
# de l'API sur des documents déjà bien lus par Tesseract.
AI_FALLBACK_CONFIDENCE_THRESHOLD = 0.6

# Champs renvoyés par extractor.extract_fields() qu'il n'est pas pertinent
# de demander à l'IA de vision : "type_document" est déjà connu (résultat de
# la classification, pas quelque chose à lire sur l'image), "mrz" est un
# artefact de lecture MRZ propre à l'OCR, et "categories"/"dates_detectees"
# sont des listes — l'IA de vision ne renvoie ici que des champs texte.
AI_EXCLUDED_FIELDS = {"type_document", "mrz", "categories", "dates_detectees"}
