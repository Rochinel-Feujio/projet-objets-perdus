"""
Notifications par email : envoie un message à une adresse de surveillance
(NOTIFY_EMAIL) à chaque événement important — nouveau compte créé, nouvelle
déclaration de perte, nouveau document trouvé.

Configuration via secrets Streamlit (st.secrets) ou variables
d'environnement — voir README.md, section "Notifications par email" :
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM (optionnel,
  reprend SMTP_USER par défaut), NOTIFY_EMAIL (destinataire des notifications).

Si cette configuration est absente ou incomplète, les notifications sont
silencieusement désactivées — l'application continue de fonctionner
normalement, comme pour DATABASE_URL (voir storage.py). Un échec d'envoi
(mauvais mot de passe, réseau...) n'interrompt jamais le flux principal de
l'application : send_notification() ne lève jamais d'exception.
"""

import os
import smtplib
import ssl
from email.message import EmailMessage


def _get(key: str):
    """Lit une clé de config depuis les secrets Streamlit si disponibles,
    sinon depuis une variable d'environnement du même nom."""
    try:
        import streamlit as st

        try:
            if key in st.secrets:
                return st.secrets[key]
        except Exception:
            pass
    except Exception:
        pass
    return os.environ.get(key)


def _config():
    smtp_user = _get("SMTP_USER")
    return {
        "host": _get("SMTP_HOST"),
        "port": int(_get("SMTP_PORT") or 465),
        "user": smtp_user,
        "password": _get("SMTP_PASSWORD"),
        "from_addr": _get("SMTP_FROM") or smtp_user,
        "notify_to": _get("NOTIFY_EMAIL"),
    }


def is_configured() -> bool:
    cfg = _config()
    return bool(cfg["host"] and cfg["user"] and cfg["password"] and cfg["notify_to"])


def send_notification(subject: str, body: str) -> bool:
    """Envoie un email de notification à NOTIFY_EMAIL. Renvoie True si
    l'envoi a réussi, False si la configuration est absente ou si l'envoi a
    échoué pour une raison quelconque — cette fonction ne lève jamais
    d'exception, pour ne jamais faire planter l'action principale
    (création de compte, déclaration...) à cause d'un souci d'email."""
    cfg = _config()
    if not is_configured():
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = cfg["from_addr"]
        msg["To"] = cfg["notify_to"]
        msg.set_content(body)

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(cfg["host"], cfg["port"], context=context, timeout=10) as server:
            server.login(cfg["user"], cfg["password"])
            server.send_message(msg)
        return True
    except Exception:
        return False
