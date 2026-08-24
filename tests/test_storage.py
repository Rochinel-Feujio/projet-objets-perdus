"""
Tests unitaires du stockage et du rapprochement déclarations perdues <->
documents retrouvés — utilisent une base SQLite temporaire (pas la base
"documents.db" réelle), pas besoin d'image.

Lancer avec : python -m pytest tests/test_storage.py -v
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from storage import (
    save_document,
    save_declaration,
    find_matching_documents,
    find_matching_declarations,
    _fields_match,
    create_user,
    authenticate_user,
    get_user,
    list_found_documents,
    list_user_documents,
    list_user_declarations,
    get_document,
    export_all_data,
)


def _tmp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)  # on veut juste un chemin libre, pas un fichier vide
    return path


def test_fields_match_on_numero():
    assert _fields_match({"numero": "12345678901234567"}, {"numero": "12345678901234567"}) == "numero"


def test_fields_match_on_nom_case_and_spacing_insensitive():
    assert _fields_match({"nom": "  jean   dupont "}, {"nom": "JEAN DUPONT"}) == "nom"


def test_fields_no_match():
    assert _fields_match({"nom": "JEAN DUPONT"}, {"nom": "PAUL MARTIN"}) is None


def test_fields_match_prefers_numero_over_nom_mismatch():
    # Même si le nom diffère (ex. faute de frappe / homonyme), un numéro
    # identique doit suffire à établir la correspondance.
    a = {"nom": "JEAN DUPONT", "numero": "111"}
    b = {"nom": "J DUPONT", "numero": "111"}
    assert _fields_match(a, b) == "numero"


def test_declaration_matches_existing_found_document():
    db_path = _tmp_db()
    try:
        save_document(
            fields={"type_document": "CNI", "nom": "MARIE NGONO", "numero": "12345678901234567"},
            confidence=0.8,
            alerts=[],
            source_image="photo.jpg",
            db_path=db_path,
        )
        matches = find_matching_documents(
            "CNI", {"nom": "MARIE NGONO", "numero": "12345678901234567"}, db_path=db_path
        )
        assert len(matches) == 1
        assert matches[0]["matched_on"] == "numero"
    finally:
        os.unlink(db_path)


def test_found_document_matches_pending_declaration():
    db_path = _tmp_db()
    try:
        save_declaration(
            type_document="PERMIS",
            fields={"type_document": "PERMIS", "nom": "PAUL ETOUNDI"},
            lieu_perte="Douala",
            date_perte="2026-08-01",
            contact_nom="Paul Etoundi",
            contact_telephone="699000000",
            contact_email="",
            db_path=db_path,
        )
        matches = find_matching_declarations(
            "PERMIS", {"nom": "PAUL ETOUNDI"}, db_path=db_path
        )
        assert len(matches) == 1
        assert matches[0]["matched_on"] == "nom"
        assert matches[0]["contact_telephone"] == "699000000"
    finally:
        os.unlink(db_path)


def test_no_cross_type_match():
    # Même nom, mais types de documents différents -> pas de rapprochement.
    db_path = _tmp_db()
    try:
        save_document(
            fields={"type_document": "CNI", "nom": "SAMUEL MBIDA"},
            confidence=0.7,
            alerts=[],
            source_image="photo.jpg",
            db_path=db_path,
        )
        matches = find_matching_documents("PERMIS", {"nom": "SAMUEL MBIDA"}, db_path=db_path)
        assert matches == []
    finally:
        os.unlink(db_path)


def test_create_and_authenticate_user():
    db_path = _tmp_db()
    try:
        user_id = create_user(
            "Marie Ngono", "Marie@Example.com", "motdepasse123", "699000000", db_path=db_path
        )
        assert user_id is not None

        user = authenticate_user("marie@example.com", "motdepasse123", db_path=db_path)
        assert user is not None
        assert user["id"] == user_id
        assert user["nom"] == "Marie Ngono"
        assert user["email"] == "marie@example.com"
        # Le hash/sel ne doit jamais être exposé par authenticate_user().
        assert "password_hash" not in user
        assert "password_salt" not in user

        assert authenticate_user("marie@example.com", "mauvais_mdp", db_path=db_path) is None
        assert authenticate_user("inconnu@example.com", "motdepasse123", db_path=db_path) is None
    finally:
        os.unlink(db_path)


def test_create_user_duplicate_email_rejected():
    db_path = _tmp_db()
    try:
        create_user("Paul Etoundi", "paul@example.com", "motdepasse123", db_path=db_path)
        try:
            create_user("Paul Bis", "paul@example.com", "autremdp123", db_path=db_path)
            assert False, "un email en double aurait dû être rejeté"
        except ValueError:
            pass
    finally:
        os.unlink(db_path)


def test_create_user_short_password_rejected():
    db_path = _tmp_db()
    try:
        try:
            create_user("Test", "test@example.com", "123", db_path=db_path)
            assert False, "un mot de passe trop court aurait dû être rejeté"
        except ValueError:
            pass
    finally:
        # La validation échoue avant toute création de fichier DB (voir
        # create_user) : rien à nettoyer dans ce cas précis.
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_get_user():
    db_path = _tmp_db()
    try:
        user_id = create_user("Samuel Mbida", "samuel@example.com", "motdepasse123", db_path=db_path)
        user = get_user(user_id, db_path=db_path)
        assert user["nom"] == "Samuel Mbida"
        assert get_user(999999, db_path=db_path) is None
    finally:
        os.unlink(db_path)


def test_list_found_documents_and_get_document():
    db_path = _tmp_db()
    try:
        doc_id = save_document(
            fields={"type_document": "CNI", "nom": "JEAN DUPONT", "numero": "111"},
            confidence=0.9,
            alerts=[],
            source_image="photo.jpg",
            db_path=db_path,
            user_id=42,
            finder_contact="699111222",
        )
        feed = list_found_documents(db_path=db_path)
        assert len(feed) == 1
        assert feed[0]["id"] == doc_id
        assert feed[0]["fields"]["nom"] == "JEAN DUPONT"
        assert feed[0]["finder_contact"] == "699111222"

        doc = get_document(doc_id, db_path=db_path)
        assert doc["fields"]["nom"] == "JEAN DUPONT"
        assert get_document(999999, db_path=db_path) is None
    finally:
        os.unlink(db_path)


def test_list_user_documents_and_declarations():
    db_path = _tmp_db()
    try:
        user_id = create_user("Alice Fotso", "alice@example.com", "motdepasse123", db_path=db_path)

        save_document(
            fields={"type_document": "CNI", "nom": "ALICE FOTSO"},
            confidence=0.9,
            alerts=[],
            source_image="photo.jpg",
            db_path=db_path,
            user_id=user_id,
        )
        # Document trouvé par quelqu'un d'autre : ne doit pas apparaître.
        save_document(
            fields={"type_document": "CNI", "nom": "AUTRE PERSONNE"},
            confidence=0.9,
            alerts=[],
            source_image="photo2.jpg",
            db_path=db_path,
            user_id=999,
        )
        save_declaration(
            type_document="PASSEPORT",
            fields={"type_document": "PASSEPORT", "nom": "ALICE FOTSO"},
            lieu_perte="Yaoundé",
            date_perte="2026-08-01",
            contact_nom="Alice Fotso",
            contact_telephone="690000000",
            contact_email="",
            db_path=db_path,
            user_id=user_id,
        )

        my_docs = list_user_documents(user_id, db_path=db_path)
        assert len(my_docs) == 1
        assert my_docs[0]["fields"]["nom"] == "ALICE FOTSO"

        my_decls = list_user_declarations(user_id, db_path=db_path)
        assert len(my_decls) == 1
        assert my_decls[0]["type_document"] == "PASSEPORT"
    finally:
        os.unlink(db_path)


def test_export_all_data_includes_everything_but_no_password_fields():
    db_path = _tmp_db()
    try:
        user_id = create_user("Backup Tester", "backup@example.com", "motdepasse123", db_path=db_path)
        save_document(
            fields={"type_document": "CNI", "nom": "BACKUP DOC"},
            confidence=0.9,
            alerts=[],
            source_image="photo.jpg",
            db_path=db_path,
            user_id=user_id,
        )
        save_declaration(
            type_document="PASSEPORT",
            fields={"type_document": "PASSEPORT", "nom": "BACKUP DECL"},
            lieu_perte="Douala",
            date_perte="2026-08-01",
            contact_nom="Backup Tester",
            contact_telephone="690000000",
            contact_email="",
            db_path=db_path,
            user_id=user_id,
        )

        export = export_all_data(db_path=db_path)
        assert "exported_at" in export
        assert len(export["documents"]) == 1
        assert export["documents"][0]["fields"]["nom"] == "BACKUP DOC"
        assert len(export["declarations"]) == 1
        assert export["declarations"][0]["fields"]["nom"] == "BACKUP DECL"
        assert len(export["users"]) == 1
        assert export["users"][0]["email"] == "backup@example.com"
        assert "password_hash" not in export["users"][0]
        assert "password_salt" not in export["users"][0]

        # Doit être sérialisable en JSON tel quel (c'est l'usage réel : bouton
        # de téléchargement dans l'écran Profil).
        import json
        json.dumps(export, ensure_ascii=False)
    finally:
        os.unlink(db_path)


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    passed, failed = 0, 0
    for t in tests:
        try:
            t()
            print(f"OK   {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed} réussis, {failed} échoués")
    sys.exit(1 if failed else 0)
