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
