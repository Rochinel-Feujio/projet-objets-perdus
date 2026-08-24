"""
Stockage des documents identifiés — deux backends possibles, choisis
automatiquement selon la configuration :

  - PostgreSQL (recommandé pour une vraie persistance) si une URL de
    connexion est fournie via `st.secrets["DATABASE_URL"]` (Streamlit) ou
    la variable d'environnement `DATABASE_URL`. Un service comme Supabase
    (offre gratuite) convient parfaitement — voir README.md, section
    "Base de données persistante (PostgreSQL)".
  - SQLite local (fichier `documents.db`, `config.DB_PATH`) sinon — c'est
    le mode utilisé automatiquement par les tests (isolation via un fichier
    temporaire différent par test) et pratique pour développer en local
    sans rien configurer.

Le reste du code (app.py, main.py) ne sait pas quel backend est actif : les
fonctions ci-dessous ont exactement la même signature dans les deux cas.
"""

import hashlib
import json
import os
import secrets
from datetime import datetime
from functools import lru_cache

import sqlalchemy as sa
from sqlalchemy import Column, Float, Integer, MetaData, Table, Text

from config import DB_PATH

metadata = MetaData()

documents_table = Table(
    "documents",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("type_document", Text, nullable=False),
    Column("confidence", Float),
    Column("fields_json", Text, nullable=False),
    Column("alerts_json", Text),
    Column("source_image", Text),
    Column("created_at", Text, nullable=False),
    Column("user_id", Integer),
    Column("finder_contact", Text),
)

declarations_table = Table(
    "declarations",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("type_document", Text, nullable=False),
    Column("fields_json", Text, nullable=False),
    Column("lieu_perte", Text),
    Column("date_perte", Text),
    Column("contact_nom", Text),
    Column("contact_telephone", Text),
    Column("contact_email", Text),
    Column("statut", Text, nullable=False, server_default="en_attente"),
    Column("created_at", Text, nullable=False),
    Column("user_id", Integer),
)

users_table = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("nom", Text, nullable=False),
    Column("email", Text, nullable=False, unique=True),
    Column("telephone", Text),
    Column("password_hash", Text, nullable=False),
    Column("password_salt", Text, nullable=False),
    Column("created_at", Text, nullable=False),
)


# ---------------------------------------------------------------------------
# Résolution du backend actif + gestion du schéma.
# ---------------------------------------------------------------------------

def _database_url():
    """URL de connexion Postgres si configurée, sinon None (repli SQLite).
    Cherche d'abord dans les secrets Streamlit (st.secrets["DATABASE_URL"]),
    puis dans la variable d'environnement DATABASE_URL — utile pour lancer
    main.py en CLI ou exécuter les tests sans dépendre de Streamlit."""
    try:
        import streamlit as st

        try:
            if "DATABASE_URL" in st.secrets:
                return st.secrets["DATABASE_URL"]
        except Exception:
            # st.secrets lève une exception s'il n'y a pas de fichier
            # secrets.toml du tout (cas normal en local sans Postgres) —
            # on se rabat simplement sur la variable d'environnement.
            pass
    except Exception:
        pass
    return os.environ.get("DATABASE_URL")


def _ensure_schema(engine):
    """Crée les tables manquantes (metadata.create_all, portable
    SQLite/Postgres) puis ajoute les colonnes manquantes sur des tables déjà
    existantes avec un schéma plus ancien (migration légère, pour ne pas
    perdre les données d'une base SQLite locale créée par une version
    précédente du prototype)."""
    metadata.create_all(engine, checkfirst=True)
    inspector = sa.inspect(engine)
    for table in metadata.tables.values():
        existing_cols = {c["name"] for c in inspector.get_columns(table.name)}
        for col in table.columns:
            if col.name in existing_cols:
                continue
            type_sql = "INTEGER" if isinstance(col.type, Integer) else "TEXT"
            with engine.begin() as conn:
                conn.execute(sa.text(f"ALTER TABLE {table.name} ADD COLUMN {col.name} {type_sql}"))


@lru_cache(maxsize=None)
def _engine_for(db_path: str):
    """Un moteur SQLAlchemy par cible. Si DATABASE_URL est configurée, tous
    les appels partagent le même moteur Postgres (db_path est alors ignoré
    — il n'y a qu'une seule base). Sinon, chaque valeur de db_path obtient
    son propre moteur SQLite sur ce fichier : c'est ce qui permet aux tests
    de s'isoler les uns des autres avec un fichier temporaire différent à
    chaque fois, exactement comme avant ce passage à SQLAlchemy."""
    url = _database_url()
    if url:
        engine = sa.create_engine(url, pool_pre_ping=True, future=True)
    else:
        engine = sa.create_engine(f"sqlite:///{db_path}", future=True)
    _ensure_schema(engine)
    return engine


def init_db(db_path: str = DB_PATH):
    """Conservé pour compatibilité : garantit que le schéma existe et
    renvoie le moteur SQLAlchemy actif (Postgres ou SQLite selon la config)."""
    return _engine_for(db_path)


def init_declarations_table(db_path: str = DB_PATH):
    return _engine_for(db_path)


def init_users_table(db_path: str = DB_PATH):
    return _engine_for(db_path)


# ---------------------------------------------------------------------------
# Documents retrouvés.
# ---------------------------------------------------------------------------

def save_document(
    fields: dict,
    confidence: float,
    alerts: list,
    source_image: str,
    db_path: str = DB_PATH,
    user_id: int = None,
    finder_contact: str = None,
) -> int:
    engine = _engine_for(db_path)
    with engine.begin() as conn:
        result = conn.execute(
            documents_table.insert().values(
                type_document=fields.get("type_document"),
                confidence=confidence,
                fields_json=json.dumps(fields, ensure_ascii=False),
                alerts_json=json.dumps(alerts, ensure_ascii=False),
                source_image=source_image,
                created_at=datetime.now().isoformat(timespec="seconds"),
                user_id=user_id,
                finder_contact=finder_contact,
            )
        )
        return result.inserted_primary_key[0]


def find_by_field_value(value: str, db_path: str = DB_PATH):
    """Recherche simple : renvoie les documents dont le JSON contient la valeur donnée
    (utile pour un premier prototype de correspondance objets perdus / retrouvés)."""
    engine = _engine_for(db_path)
    with engine.begin() as conn:
        rows = conn.execute(
            documents_table.select().where(documents_table.c.fields_json.like(f"%{value}%"))
        ).mappings().all()
    return [dict(row) for row in rows]


def _row_to_document(row) -> dict:
    item = dict(row)
    item["fields"] = json.loads(item["fields_json"]) if item.get("fields_json") else {}
    item["alerts"] = json.loads(item["alerts_json"]) if item.get("alerts_json") else []
    return item


def get_document(doc_id: int, db_path: str = DB_PATH):
    """Un document retrouvé par son id (pour l'écran de détail)."""
    engine = _engine_for(db_path)
    with engine.begin() as conn:
        row = conn.execute(
            documents_table.select().where(documents_table.c.id == doc_id)
        ).mappings().first()
    return _row_to_document(row) if row else None


def list_found_documents(limit: int = 100, db_path: str = DB_PATH):
    """Fil "Accueil" : les documents retrouvés les plus récents, tous
    utilisateurs confondus (public — c'est le principe même de la
    plateforme : que la personne qui a perdu son document puisse le
    reconnaître dans la liste)."""
    engine = _engine_for(db_path)
    with engine.begin() as conn:
        rows = conn.execute(
            documents_table.select()
            .order_by(documents_table.c.created_at.desc())
            .limit(limit)
        ).mappings().all()
    return [_row_to_document(row) for row in rows]


def list_user_documents(user_id: int, db_path: str = DB_PATH):
    """Documents retrouvés et enregistrés par cet utilisateur (onglet
    "Trouvés" du tableau de bord "Mes déclarations")."""
    engine = _engine_for(db_path)
    with engine.begin() as conn:
        rows = conn.execute(
            documents_table.select()
            .where(documents_table.c.user_id == user_id)
            .order_by(documents_table.c.created_at.desc())
        ).mappings().all()
    return [_row_to_document(row) for row in rows]


# ---------------------------------------------------------------------------
# Déclarations de perte : une personne qui a perdu un document (mais n'a donc
# pas de photo à déposer) renseigne ce qu'elle sait sur ce document, pour être
# recontactée si un document correspondant est retrouvé et scanné plus tard.
# ---------------------------------------------------------------------------

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
    engine = _engine_for(db_path)
    with engine.begin() as conn:
        result = conn.execute(
            declarations_table.insert().values(
                type_document=type_document,
                fields_json=json.dumps(fields, ensure_ascii=False),
                lieu_perte=lieu_perte,
                date_perte=date_perte,
                contact_nom=contact_nom,
                contact_telephone=contact_telephone,
                contact_email=contact_email,
                statut="en_attente",
                created_at=datetime.now().isoformat(timespec="seconds"),
                user_id=user_id,
            )
        )
        return result.inserted_primary_key[0]


def _row_to_declaration(row) -> dict:
    item = dict(row)
    item["fields"] = json.loads(item["fields_json"]) if item.get("fields_json") else {}
    return item


def list_user_declarations(user_id: int, db_path: str = DB_PATH):
    """Déclarations de perte faites par cet utilisateur (onglet "Perdus" du
    tableau de bord "Mes déclarations")."""
    engine = _engine_for(db_path)
    with engine.begin() as conn:
        rows = conn.execute(
            declarations_table.select()
            .where(declarations_table.c.user_id == user_id)
            .order_by(declarations_table.c.created_at.desc())
        ).mappings().all()
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
    engine = _engine_for(db_path)
    with engine.begin() as conn:
        rows = conn.execute(
            documents_table.select().where(documents_table.c.type_document == type_document)
        ).mappings().all()

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
    engine = _engine_for(db_path)
    with engine.begin() as conn:
        rows = conn.execute(
            declarations_table.select().where(
                (declarations_table.c.type_document == type_document)
                & (declarations_table.c.statut == "en_attente")
            )
        ).mappings().all()

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

    engine = _engine_for(db_path)
    with engine.begin() as conn:
        existing = conn.execute(
            users_table.select().where(users_table.c.email == email_norm)
        ).first()
        if existing:
            raise ValueError("Un compte existe déjà avec cet email.")

        salt_hex, hash_hex = _hash_password(password)
        result = conn.execute(
            users_table.insert().values(
                nom=nom,
                email=email_norm,
                telephone=(telephone or "").strip(),
                password_hash=hash_hex,
                password_salt=salt_hex,
                created_at=datetime.now().isoformat(timespec="seconds"),
            )
        )
        return result.inserted_primary_key[0]


def authenticate_user(email: str, password: str, db_path: str = DB_PATH):
    """Renvoie le dict utilisateur (sans le hash) si email/mot de passe sont
    corrects, sinon None."""
    email_norm = (email or "").strip().lower()
    engine = _engine_for(db_path)
    with engine.begin() as conn:
        row = conn.execute(
            users_table.select().where(users_table.c.email == email_norm)
        ).mappings().first()
    if not row or not password:
        return None
    _, hash_hex = _hash_password(password, row["password_salt"])
    if not secrets.compare_digest(hash_hex, row["password_hash"]):
        return None
    return _public_user(row)


def get_user(user_id: int, db_path: str = DB_PATH):
    engine = _engine_for(db_path)
    with engine.begin() as conn:
        row = conn.execute(
            users_table.select().where(users_table.c.id == user_id)
        ).mappings().first()
    return _public_user(row) if row else None
