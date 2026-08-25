"""
Tests unitaires des notifications par email (notifications.py). N'envoie
jamais de vrai email : vérifie seulement le comportement "non configuré"
(désactivation silencieuse) et le comportement en cas d'échec d'envoi
(jamais d'exception propagée).

Lancer avec : python -m pytest tests/test_notifications.py -v
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import notifications


def _clear_env(monkeypatch):
    for key in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM", "NOTIFY_EMAIL"):
        monkeypatch.delenv(key, raising=False)


def test_not_configured_by_default(monkeypatch):
    _clear_env(monkeypatch)
    assert notifications.is_configured() is False


def test_send_notification_returns_false_when_not_configured(monkeypatch):
    _clear_env(monkeypatch)
    assert notifications.send_notification("Sujet", "Corps") is False


def test_is_configured_true_when_all_keys_present(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "bot@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("NOTIFY_EMAIL", "owner@example.com")
    assert notifications.is_configured() is True


def test_is_configured_false_when_one_key_missing(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "bot@example.com")
    # SMTP_PASSWORD manquant, NOTIFY_EMAIL manquant.
    assert notifications.is_configured() is False


def test_send_notification_never_raises_on_connection_failure(monkeypatch):
    """Même configuré, un hôte SMTP injoignable ne doit jamais faire
    remonter d'exception — juste renvoyer False."""
    _clear_env(monkeypatch)
    monkeypatch.setenv("SMTP_HOST", "smtp.invalid.example.invalid")
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.setenv("SMTP_USER", "bot@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("NOTIFY_EMAIL", "owner@example.com")
    result = notifications.send_notification("Sujet", "Corps")
    assert result is False


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
