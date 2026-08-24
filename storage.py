"""
Stockage des documents identifiés — SQLite pour ce prototype.
À remplacer/brancher sur la base de données réelle du système
(PostgreSQL/MySQL...) une fois l'architecture backend confirmée.
"""

import sqlite3
import json
from datetime import datetime

from config import DB_PATH


def init_db(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type_document TEXT NOT NULL,
            confidence REAL,
            fields_json TEXT NOT NULL,
            alerts_json TEXT,
            source_image TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def save_document(fields: dict, confidence: float, alerts: list, source_image: str, db_path: str = DB_PATH) -> int:
    conn = init_db(db_path)
    cursor = conn.execute(
        """
        INSERT INTO documents (type_document, confidence, fields_json, alerts_json, source_image, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            fields.get("type_document"),
            confidence,
            json.dumps(fields, ensure_ascii=False),
            json.dumps(alerts, ensure_ascii=False),
            source_image,
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id


def find_by_field_value(value: str, db_path: str = DB_PATH):
    """Recherche simple : renvoie les documents dont le JSON contient la valeur donnée
    (utile pour un premier prototype de correspondance objets perdus / retrouvés)."""
    conn = init_db(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM documents WHERE fields_json LIKE ?", (f"%{value}%",)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Déclarations de perte : une personne qui a perdu un document (mais n'a donc
# pas de photo à déposer) renseigne ce qu'elle sait sur ce document, pour être
# recontactée si un document correspondant est retrouvé et scanné plus tard.
# ---------------------------------------------------------------------------

def init_declarations_table(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS declarations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type_document TEXT NOT NULL,
            fields_json TEXT NOT NULL,
            lieu_perte TEXT,
            date_perte TEXT,
            contact_nom TEXT,
            contact_telephone TEXT,
            contact_email TEXT,
            statut TEXT NOT NULL DEFAULT 'en_attente',
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def save_declaration(
    type_document: str,
    fields: dict,
    lieu_perte: str,
    date_perte: str,
    contact_nom: str,
    contact_telephone: str,
    contact_email: str,
    db_path: str = DB_PATH,
) -> int:
    conn = init_declarations_table(db_path)
    cursor = conn.execute(
        """
        INSERT INTO declarations
            (type_document, fields_json, lieu_perte, date_perte,
             contact_nom, contact_telephone, contact_email, statut, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'en_attente', ?)
        """,
        (
            type_document,
            json.dumps(fields, ensure_ascii=False),
            lieu_perte,
            date_perte,
            contact_nom,
            contact_telephone,
            contact_email,
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    conn.commit()
    decl_id = cursor.lastrowid
    conn.close()
    return decl_id


# Champs considérés comme des identifiants de document (comparaison stricte,
# après nettoyage des espaces) — un seul suffit pour un rapprochement fiable.
_NUMBER_FIELDS = ("numero", "numero_recepisse", "numero_matricule")


def _normalize_name(value):
    return " ".join(value.upper().split()) if value else ""


def _fields_match(fields_a: dict, fields_b: dict):
    """Compare deux jeux de champs (déclaration vs document retrouvé, ou
    l'inverse) et renvoie le nom du champ sur lequel ils correspondent, ou
    None si rien ne correspond.

    Priorité à un numéro identifiant (fiable), repli sur le nom (moins fiable
    seul — d'où son statut de dernier recours) si aucun numéro n'est
    disponible des deux côtés."""
    for num_field in _NUMBER_FIELDS:
        value_a = fields_a.get(num_field)
        value_b = fields_b.get(num_field)
        if value_a and value_b and value_a.strip() == value_b.strip():
            return num_field
    name_a = _normalize_name(fields_a.get("nom"))
    name_b = _normalize_name(fields_b.get("nom"))
    if name_a and name_a == name_b:
        return "nom"
    return None


def find_matching_documents(type_document: str, fields: dict, db_path: str = DB_PATH):
    """Depuis une déclaration de perte, cherche les documents déjà retrouvés
    et enregistrés qui pourraient lui correspondre (même type, numéro ou nom
    identique). Chaque résultat inclut 'fields' (dict) et 'matched_on'
    (le champ ayant permis le rapprochement)."""
    conn = init_db(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM documents WHERE type_document = ?", (type_document,)
    ).fetchall()
    conn.close()

    matches = []
    for row in rows:
        doc_fields = json.loads(row["fields_json"])
        matched_on = _fields_match(fields, doc_fields)
        if matched_on:
            match = dict(row)
            match["fields"] = doc_fields
            match["matched_on"] = matched_on
            matches.append(match)
    return matches


def find_matching_declarations(type_document: str, fields: dict, db_path: str = DB_PATH):
    """Symétrique de find_matching_documents() : depuis un document qui vient
    d'être retrouvé et scanné, cherche les déclarations de perte encore en
    attente qui pourraient lui correspondre."""
    conn = init_declarations_table(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM declarations WHERE type_document = ? AND statut = 'en_attente'",
        (type_document,),
    ).fetchall()
    conn.close()

    matches = []
    for row in rows:
        decl_fields = json.loads(row["fields_json"])
        matched_on = _fields_match(fields, decl_fields)
        if matched_on:
            match = dict(row)
            match["fields"] = decl_fields
            match["matched_on"] = matched_on
            matches.append(match)
    return matches
