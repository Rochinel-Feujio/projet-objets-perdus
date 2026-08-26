"""
Extraction assistée par IA de vision (Mistral AI) — un COMPLÉMENT optionnel
au pipeline OCR local (Tesseract), pas un remplacement.

Rôle : quand la lecture OCR locale a une confiance faible ou n'a pas réussi
à lire certains champs, main.analyze_document() envoie l'image du document
à un modèle de vision (Mistral) qui tente de compléter les champs manquants
et signale lui-même les incohérences qu'il repère (date d'expiration
antérieure à la date de naissance, numéro mal formaté, texte flou/coupé...).
C'est cette auto-évaluation intégrée à chaque réponse — pas juste une
lecture brute — qui en fait un comportement "agentique" léger : le résultat
inclut de quoi décider s'il faut faire confiance à un champ, et l'IA peut
signaler un problème même sur un champ que l'OCR avait déjà rempli.

La décision d'appeler l'IA (et le calcul de la liste des champs à lui
demander) se fait dans main.analyze_document(), pas ici — ce module ne fait
que l'appel lui-même et le parsing de la réponse.

Pourquoi Mistral plutôt que Gemini (Google) : le palier gratuit de Google AI
Studio n'est pas accessible depuis toutes les régions (blocage constaté
malgré un pays officiellement supporté, probablement lié à une vérification
de compte/IP côté Google) — Mistral AI (entreprise française) propose un
palier gratuit "Experiment" sans cette restriction et sans carte bancaire.

Configuration (facultative) via secrets Streamlit ou variables
d'environnement — voir README.md, section "IA de vision (optionnel)" :
  MISTRAL_API_KEY : clé API GRATUITE (palier "Experiment", aucune carte
                    bancaire requise — juste un numéro de téléphone à
                    vérifier), à obtenir sur https://console.mistral.ai
  MISTRAL_MODEL   : optionnel, modèle à utiliser (par défaut "mistral-small-latest")

Si MISTRAL_API_KEY est absente, cette fonctionnalité est silencieusement
désactivée — le pipeline continue de fonctionner uniquement avec l'OCR
local, exactement comme avant. Un échec d'appel (réseau, quota gratuit
dépassé, réponse invalide, dépendance non installée...) ne fait JAMAIS
planter l'analyse principale : extract_fields_with_ai() renvoie toujours
None dans ce cas, jamais d'exception.
"""

import base64
import json
import os
import re

try:
    from mistralai.client import Mistral
except ImportError:  # dépendance optionnelle — voir requirements.txt
    Mistral = None


def _get(key: str):
    """Lit une clé de config depuis les secrets Streamlit si disponibles,
    sinon depuis une variable d'environnement du même nom (même pattern que
    storage._database_url() et notifications._get())."""
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


def _api_key():
    return _get("MISTRAL_API_KEY")


def _model_name():
    return _get("MISTRAL_MODEL") or "mistral-small-latest"


def is_configured() -> bool:
    return bool(_api_key())


def _build_prompt(type_document_label: str, field_keys: list) -> str:
    fields_schema = ", ".join(f'"{k}": "..."' for k in field_keys)
    fields_list = ", ".join(field_keys)
    return (
        "Tu es un assistant d'extraction de données pour un document "
        f"administratif camerounais de type « {type_document_label} ». "
        "Regarde attentivement l'image fournie et réponds UNIQUEMENT avec un "
        "objet JSON de la forme exacte suivante (aucun texte autour) :\n"
        "{\n"
        f'  "champs": {{{fields_schema}}},\n'
        '  "confiance": 0.0,\n'
        '  "remarques": ["..."]\n'
        "}\n\n"
        f"- \"champs\" doit contenir EXACTEMENT ces clés : {fields_list}. "
        "Mets `null` (pas une chaîne vide) pour un champ illisible ou absent "
        "de ce document — n'invente jamais une valeur que tu ne peux pas "
        "lire avec certitude sur l'image.\n"
        "- \"confiance\" est un nombre entre 0 et 1 représentant ta confiance "
        "globale dans l'exactitude de cette lecture.\n"
        "- \"remarques\" est une liste de courtes phrases en français "
        "signalant toute incohérence que tu repères (ex. date d'expiration "
        "antérieure à la date de naissance, numéro qui ne respecte "
        "manifestement pas un format attendu, texte flou ou coupé) — liste "
        "vide si rien à signaler."
    )


def _parse_json_response(text):
    if not text:
        return None
    match = re.search(r"\{.*\}", text.strip(), re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except (json.JSONDecodeError, TypeError):
        return None


def extract_fields_with_ai(image_path: str, type_document_label: str, field_keys: list):
    """Envoie l'image du document à Mistral pour extraction/vérification des
    champs listés dans `field_keys`. Renvoie un dict
    {"champs": {...}, "confiance": float|None, "remarques": [...]} en cas de
    succès, ou None si l'IA n'est pas configurée, si la dépendance
    `mistralai` n'est pas installée, ou si l'appel échoue pour une raison
    quelconque — voir docstring du module, jamais d'exception propagée."""
    if not is_configured() or not field_keys or Mistral is None:
        return None
    try:
        client = Mistral(api_key=_api_key())

        with open(image_path, "rb") as f:
            image_bytes = f.read()
        ext = os.path.splitext(image_path)[1].lower()
        mime_type = "image/png" if ext == ".png" else "image/jpeg"
        b64_image = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:{mime_type};base64,{b64_image}"

        prompt = _build_prompt(type_document_label, field_keys)
        response = client.chat.complete(
            model=_model_name(),
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": data_url},
                    ],
                }
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        text = response.choices[0].message.content
        parsed = _parse_json_response(text)
        if not parsed or not isinstance(parsed.get("champs"), dict):
            return None

        champs = {k: parsed["champs"].get(k) for k in field_keys}
        # Le modèle répond parfois par une chaîne vide ou le mot "null"
        # plutôt qu'un vrai null JSON — on normalise vers None dans les deux cas.
        champs = {
            k: (v if v not in ("", "null", "None") else None)
            for k, v in champs.items()
        }

        try:
            confiance = float(parsed.get("confiance"))
        except (TypeError, ValueError):
            confiance = None

        remarques = parsed.get("remarques")
        if not isinstance(remarques, list):
            remarques = []
        remarques = [str(r) for r in remarques if r]

        return {"champs": champs, "confiance": confiance, "remarques": remarques}
    except Exception:
        return None
