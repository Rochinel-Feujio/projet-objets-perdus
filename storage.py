"""
Stockage des documents identifiés — SQLite pour ce prototype.
À remplacer/brancher sur la base de données réelle du système
(PostgreSQL/MySQL...) une fois l'architecture backend confirmée.
"""

import hashlib
import secrets
import sqlite3
import json
from datetime import datetime

from config import DB_PATH


def _ensure_column(conn, table: str, column: str, coltype_sql: str):
    """Ajoute une colonne à une table existante si elle n'existe pas déjà
    (migration légère pour ce prototype SQLite — pas de vrai outil de
    migration comme Alembic à ce stade)."""
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype_sql}")


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
    # Migration : compte de la personne qui a retrouvé le document (peut être
    # NULL si retrouvé anonymement) + un moyen de contact affiché à la
    # personne qui recherche son document ("voir les coordonnées").
    _ensure_column(conn, "documents", "user_id", "INTEGER")
    _ensure_column(conn, "documents", "finder_contact", "TEXT")
    conn.commit()
    return conn


def save_document(
    fields: dict,
    confidence: float,
    alerts: list,
    source_image: str,
    db_path: str = DB_PATH,
    user_id: int = None,
    finder_contact: str = None,
) -> int:
    conn = init_db(db_path)
    cursor = conn.execute(
        """
        INSERT INTO documents
            (type_document, confidence, fields_json, alerts_json, source_image,
             created_at, user_id, finder_contact)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            fields.get("type_document"),
            confidence,
            json.dumps(fields, ensure_ascii=False),
            json.dumps(alerts, ensure_ascii=False),
            source_image,
            datetime.now().isoformat(timespec="seconds"),
            user_id,
            finder_contact,
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


def _row_to_document(row) -> dict:
    item = dict(row)
    item["fields"] = json.loads(item["fields_json"]) if item.get("fields_json") else {}
    item["alerts"] = json.loads(item["alerts_json"]) if item.get("alerts_json") else []
    return item


def get_document(doc_id: int, db_path: str = DB_PATH):
    """Un document retrouvé par son id (pour l'écran de détail)."""
    conn = init_db(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    conn.close()
    return _row_to_document(row) if row else None


def list_found_documents(limit: int = 100, db_path: str = DB_PATH):
    """Fil "Accueil" : les documents retrouvés les plus récents, tous
    utilisateurs confondus (public — c'est le principe même de la
    plateforme : que la personne qui a perdu son document puisse le
    reconnaître dans la liste)."""
    conn = init_db(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM documents ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [_row_to_document(row) for row in rows]


def list_user_documents(user_id: int, db_path: str = DB_PATH):
    """Documents retrouvés et enregistrés par cet utilisateur (onglet
    "Trouvés" du tableau de bord "Mes déclarations")."""
    conn = init_db(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM documents WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [_row_to_document(row) for row in rows]


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
    # Migration : compte de la personne qui déclare (peut être NULL si
    # déclaration faite sans compte, gardé possible pour ce prototype).
    _ensure_column(conn, "declarations", "user_id", "INTEGER")
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
    user_id: int = None,
) -> int:
    conn = init_declarations_table(db_path)
    cursor = conn.execute(
        """
        INSERT INTO declarations
            (type_document, fields_json, lieu_perte, date_perte,
             contact_nom, contact_telephone, contact_email, statut, created_at, user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'en_attente', ?, ?)
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
            user_id,
        ),
    )
    conn.commit()
    decl_id = cursor.lastrowid
    conn.close()
    return decl_id


def _row_to_declaration(row) -> dict:
    item = dict(row)
    item["fields"] = json.loads(item["fields_json"]) if item.get("fields_json") else {}
    return item


def list_user_declarations(user_id: int, db_path: str = DB_PATH):
    """Déclarations de perte faites par cet utilisateur (onglet "Perdus" du
    tableau de bord "Mes déclarations")."""
    conn = init_declarations_table(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM declarations WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [_row_to_declaration(row) for row in rows]


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


# ---------------------------------------------------------------------------
# Comptes utilisateurs : nécessaires pour "Mes déclarations" (tableau de bord
# personnel) et pour associer un moyen de contact aux documents retrouvés.
#
# ⚠️ Prototype uniquement : hachage salé PBKDF2-HMAC-SHA256 fait maison, pas
# de vérification d'email, pas de limitation de tentatives, pas de politique
# de mot de passe. À remplacer par un vrai système d'authentification
# (ex. gestionnaire dédié + bcrypt/argon2, envoi d'email de confirmation)
# avant tout usage en production — voir "Limites connues" dans le README.
# ---------------------------------------------------------------------------

def init_users_table(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            telephone TEXT,
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def _hash_password(password: str, salt_hex: str = None):
    salt_hex = salt_hex or secrets.token_hex(16)
    salt_bytes = bytes.fromhex(salt_hex)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, 100_000)
    return salt_hex, digest.hex()


def _public_user(row) -> dict:
    """Vue d'un utilisateur sans les champs sensibles (hash/sel)."""
    return {
        "id": row["id"],
        "nom": row["nom"],
        "email": row["email"],
        "telephone": row["telephone"],
    }


def create_user(nom: str, email: str, password: str, telephone: str = "", db_path: str = DB_PATH) -> int:
    """Crée un compte. Lève ValueError si l'email est déjà utilisé, si le nom
    ou le mot de passe sont vides, ou si le mot de passe est trop court."""
    nom = (nom or "").strip()
    email_norm = (email or "").strip().lower()
    if not nom:
        raise ValueError("Le nom est obligatoire.")
    if not email_norm or "@" not in email_norm:
        raise ValueError("Adresse email invalide.")
    if not password or len(password) < 6:
        raise ValueError("Le mot de passe doit contenir au moins 6 caractères.")

    conn = init_users_table(db_path)
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (email_norm,)).fetchone()
    if existing:
        conn.close()
        raise ValueError("Un compte existe déjà avec cet email.")

    salt_hex, hash_hex = _hash_password(password)
    cursor = conn.execute(
        """
        INSERT INTO users (nom, email, telephone, password_hash, password_salt, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            nom,
            email_norm,
            (telephone or "").strip(),
            hash_hex,
            salt_hex,
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id


def authenticate_user(email: str, password: str, db_path: str = DB_PATH):
    """Renvoie le dict utilisateur (sans le hash) si email/mot de passe sont
    corrects, sinon None."""
    email_norm = (email or "").strip().lower()
    conn = init_users_table(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email_norm,)).fetchone()
    conn.close()
    if not row or not password:
        return None
    _, hash_hex = _hash_password(password, row["password_salt"])
    if not secrets.compare_digest(hash_hex, row["password_hash"]):
        return None
    return _public_user(row)


def get_user(user_id: int, db_path: str = DB_PATH):
    conn = init_users_table(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return _public_user(row) if row else None
