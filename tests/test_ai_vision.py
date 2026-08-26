"""
Tests unitaires du complément IA de vision (ai_vision.py). N'appelle jamais
la vraie API Mistral : le client `mistralai.client.Mistral` est entièrement
simulé (classes _Fake*) pour vérifier le comportement de configuration, la
construction du prompt, le parsing de la réponse, et la garantie qu'aucune
exception ne remonte jamais jusqu'à l'appelant (main.analyze_document).

Lancer avec : python -m pytest tests/test_ai_vision.py -v
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import ai_vision


def _clear_env(monkeypatch):
    for key in ("MISTRAL_API_KEY", "MISTRAL_MODEL"):
        monkeypatch.delenv(key, raising=False)


def _write_tmp_image(tmp_path):
    path = os.path.join(str(tmp_path), "doc.jpg")
    with open(path, "wb") as f:
        f.write(b"\xff\xd8\xff\xe0fake-jpeg-bytes-not-a-real-image")
    return path


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def test_not_configured_by_default(monkeypatch):
    _clear_env(monkeypatch)
    assert ai_vision.is_configured() is False


def test_configured_when_api_key_present(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("MISTRAL_API_KEY", "fake-key")
    assert ai_vision.is_configured() is True


def test_extract_returns_none_when_not_configured(monkeypatch, tmp_path):
    _clear_env(monkeypatch)
    image_path = _write_tmp_image(tmp_path)
    assert ai_vision.extract_fields_with_ai(image_path, "Carte Nationale d'Identité", ["nom"]) is None


def test_extract_returns_none_when_no_field_keys(monkeypatch, tmp_path):
    _clear_env(monkeypatch)
    monkeypatch.setenv("MISTRAL_API_KEY", "fake-key")
    image_path = _write_tmp_image(tmp_path)
    assert ai_vision.extract_fields_with_ai(image_path, "Carte Nationale d'Identité", []) is None


def test_extract_returns_none_when_dependency_unavailable(monkeypatch, tmp_path):
    """Si le paquet mistralai n'est pas installé (Mistral is None au niveau
    du module), on ne doit jamais planter — juste renvoyer None."""
    _clear_env(monkeypatch)
    monkeypatch.setenv("MISTRAL_API_KEY", "fake-key")
    monkeypatch.setattr(ai_vision, "Mistral", None)
    image_path = _write_tmp_image(tmp_path)
    assert ai_vision.extract_fields_with_ai(image_path, "Carte Nationale d'Identité", ["nom"]) is None


# ---------------------------------------------------------------------------
# Construction du prompt / parsing de la réponse (fonctions pures)
# ---------------------------------------------------------------------------

def test_build_prompt_contains_field_keys_and_label():
    prompt = ai_vision._build_prompt("Carte Nationale d'Identité", ["nom", "numero"])
    assert "nom" in prompt
    assert "numero" in prompt
    assert "Carte Nationale d'Identité" in prompt


def test_parse_json_response_extracts_json_block():
    text = (
        "Voici le résultat :\n```json\n"
        '{"champs": {"nom": "DUPONT"}, "confiance": 0.9, "remarques": []}'
        "\n```"
    )
    parsed = ai_vision._parse_json_response(text)
    assert parsed["champs"]["nom"] == "DUPONT"
    assert parsed["confiance"] == 0.9


def test_parse_json_response_invalid_returns_none():
    assert ai_vision._parse_json_response("pas de json ici") is None
    assert ai_vision._parse_json_response("") is None
    assert ai_vision._parse_json_response(None) is None


# ---------------------------------------------------------------------------
# Appel simulé de bout en bout (client mistralai entièrement factice)
# ---------------------------------------------------------------------------

class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeChatResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeChat:
    def __init__(self, response_text):
        self._response_text = response_text
        self.last_call = None

    def complete(self, model, messages, temperature=None, response_format=None):
        self.last_call = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "response_format": response_format,
        }
        return _FakeChatResponse(self._response_text)


class _FakeMistralClient:
    def __init__(self, response_text, api_key=None):
        self.chat = _FakeChat(response_text)


def _fake_mistral_factory(response_text):
    def _factory(api_key=None):
        return _FakeMistralClient(response_text, api_key=api_key)

    return _factory


def test_extract_fields_with_ai_success(monkeypatch, tmp_path):
    monkeypatch.setenv("MISTRAL_API_KEY", "fake-key")
    response_text = (
        '{"champs": {"nom": "FEUJIO ROCHINEL", "numero": null}, '
        '"confiance": 0.87, "remarques": ["numéro illisible"]}'
    )
    monkeypatch.setattr(ai_vision, "Mistral", _fake_mistral_factory(response_text))

    image_path = _write_tmp_image(tmp_path)
    result = ai_vision.extract_fields_with_ai(image_path, "Carte Nationale d'Identité", ["nom", "numero"])

    assert result is not None
    assert result["champs"]["nom"] == "FEUJIO ROCHINEL"
    assert result["champs"]["numero"] is None
    assert result["confiance"] == 0.87
    assert result["remarques"] == ["numéro illisible"]


def test_extract_fields_with_ai_uses_default_model_and_json_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("MISTRAL_API_KEY", "fake-key")
    response_text = '{"champs": {"nom": "DUPONT"}, "confiance": 0.5, "remarques": []}'

    captured_client = {}

    def _factory(api_key=None):
        client = _FakeMistralClient(response_text, api_key=api_key)
        captured_client["client"] = client
        return client

    monkeypatch.setattr(ai_vision, "Mistral", _factory)

    image_path = _write_tmp_image(tmp_path)
    ai_vision.extract_fields_with_ai(image_path, "Carte Nationale d'Identité", ["nom"])

    call = captured_client["client"].chat.last_call
    assert call["model"] == "mistral-small-latest"
    assert call["response_format"] == {"type": "json_object"}


def test_extract_fields_with_ai_only_returns_requested_keys(monkeypatch, tmp_path):
    """Même si la réponse contient des clés en trop, seules celles demandées
    dans field_keys doivent apparaître dans le résultat."""
    monkeypatch.setenv("MISTRAL_API_KEY", "fake-key")
    response_text = (
        '{"champs": {"nom": "DUPONT", "numero": "12345", "champ_en_trop": "x"}, '
        '"confiance": 0.5, "remarques": []}'
    )
    monkeypatch.setattr(ai_vision, "Mistral", _fake_mistral_factory(response_text))

    image_path = _write_tmp_image(tmp_path)
    result = ai_vision.extract_fields_with_ai(image_path, "Carte Nationale d'Identité", ["nom", "numero"])

    assert set(result["champs"].keys()) == {"nom", "numero"}


def test_extract_fields_with_ai_returns_none_on_unparseable_response(monkeypatch, tmp_path):
    monkeypatch.setenv("MISTRAL_API_KEY", "fake-key")
    monkeypatch.setattr(ai_vision, "Mistral", _fake_mistral_factory("ceci n'est pas du json"))

    image_path = _write_tmp_image(tmp_path)
    result = ai_vision.extract_fields_with_ai(image_path, "Carte Nationale d'Identité", ["nom"])
    assert result is None


def test_extract_fields_with_ai_never_raises_on_client_error(monkeypatch, tmp_path):
    """Un souci réseau/API (client qui lève une exception) ne doit jamais
    remonter — l'appelant (main.analyze_document) ne doit jamais planter à
    cause d'un problème côté IA."""
    monkeypatch.setenv("MISTRAL_API_KEY", "fake-key")

    def _broken_factory(api_key=None):
        raise RuntimeError("réseau indisponible")

    monkeypatch.setattr(ai_vision, "Mistral", _broken_factory)

    image_path = _write_tmp_image(tmp_path)
    result = ai_vision.extract_fields_with_ai(image_path, "Carte Nationale d'Identité", ["nom"])
    assert result is None


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
