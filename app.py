"""
Interface web (Streamlit) du prototype "Findici" : détection automatique de
documents administratifs camerounais + déclarations de perte + comptes
utilisateurs + fil des documents retrouvés + tableau de bord personnel.
Déployé sur Streamlit Community Cloud — voir README.md.
"""

import json
import os
import tempfile
import urllib.parse
from datetime import datetime

import cv2
import streamlit as st

from main import process_document, analyze_document
from pdf_input import pdf_first_page_to_image
from config import DOCUMENT_TYPES, DECLARATION_FIELDS, FIELD_LABELS
from storage import (
    save_declaration,
    save_document,
    find_matching_documents,
    find_matching_declarations,
    create_user,
    authenticate_user,
    list_found_documents,
    list_user_documents,
    list_user_declarations,
    get_document,
    export_all_data,
    get_user,
    list_all_declarations,
    list_all_users,
    get_admin_stats,
)
from notifications import send_notification


def cv2_to_rgb(image):
    """Convertit une image OpenCV (BGR) en RGB pour l'affichage Streamlit."""
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def is_pdf_upload(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() == ".pdf"


def save_uploaded_to_tmp(uploaded_file) -> str:
    """Enregistre un fichier envoyé via st.file_uploader dans un fichier
    temporaire, en conservant sa vraie extension (.pdf, .jpg, .png...) —
    indispensable pour que analyze_document()/process_document() détectent
    correctement un PDF (voir pdf_input.is_pdf, basé sur l'extension)."""
    suffix = os.path.splitext(uploaded_file.name)[1].lower() or ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getbuffer())
        return tmp.name


st.set_page_config(
    page_title="Findici — Documents Cameroun",
    page_icon="🇨🇲",
    layout="centered",
)

# ---------------------------------------------------------------------------
# Design : palette inspirée du drapeau camerounais (identique au prototype de
# détection d'origine, réutilisée pour toute l'application "Findici").
#   vert  #007A33   rouge  #CE1126   jaune/or  #FCD116
# ---------------------------------------------------------------------------
GREEN = "#007A33"
RED = "#CE1126"
GOLD = "#FCD116"
INK = "#1B1F1C"

# Emblème stylisé (écu tricolore + étoile) inspiré des armoiries du Cameroun —
# une interprétation graphique simplifiée, pas une reproduction héraldique
# exacte des armoiries officielles (épée, balance, faisceaux de licteur...).
EMBLEM_SVG = """
<svg viewBox="0 0 200 240" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <clipPath id="shieldClip">
      <path d="M40,20 L160,20 L160,110 C160,175 130,205 100,225 C70,205 40,175 40,110 Z"/>
    </clipPath>
    <filter id="emblemShadow" x="-30%" y="-30%" width="160%" height="160%">
      <feDropShadow dx="0" dy="3" stdDeviation="4" flood-color="#000" flood-opacity="0.25"/>
    </filter>
  </defs>
  <g filter="url(#emblemShadow)">
    <g clip-path="url(#shieldClip)">
      <rect x="40" y="0" width="40" height="240" fill="#007A33"/>
      <rect x="80" y="0" width="40" height="240" fill="#CE1126"/>
      <rect x="120" y="0" width="40" height="240" fill="#FCD116"/>
    </g>
    <path d="M40,20 L160,20 L160,110 C160,175 130,205 100,225 C70,205 40,175 40,110 Z"
          fill="none" stroke="#1B1F1C" stroke-width="4"/>
    <polygon points="100,53 105.0,68.12 120.92,68.20 108.08,77.63 112.93,92.80 100,83.5 87.07,92.80 91.92,77.63 79.08,68.20 95.0,68.12"
             fill="#FCD116" stroke="#1B1F1C" stroke-width="1.5"/>
  </g>
</svg>
"""

# Encodée en data URI pour l'<img> du filigrane (échappe correctement les
# guillemets, # et espaces — indispensable pour que ça s'affiche dans tous les
# navigateurs, contrairement à une simple concaténation brute).
EMBLEM_DATA_URI = "data:image/svg+xml," + urllib.parse.quote(EMBLEM_SVG)

# Version aplatie sur une seule ligne (pas de retours à la ligne) pour
# l'insertion directe dans un bloc HTML indenté : un SVG multi-lignes non
# indenté au même niveau que le reste casse le parsing Markdown de Streamlit
# et fait retomber tout le bloc en texte brut au lieu de HTML.
EMBLEM_SVG_INLINE = " ".join(line.strip() for line in EMBLEM_SVG.strip().splitlines())

st.markdown(
    f"""
    <style>
    html, body, [class*="css"] {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }}
    .stApp {{
        background-color: #FAFAF8;
    }}
    #MainMenu, footer {{visibility: hidden;}}

    /* Filigrane : l'emblème en très grand et très transparent, fixé derrière
       tout le contenu, pour un effet "papier officiel" sans gêner la lecture. */
    .cd-watermark {{
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        width: min(70vw, 640px);
        height: auto;
        opacity: 0.05;
        z-index: 0;
        pointer-events: none;
    }}
    .stApp > header, .block-container {{
        position: relative;
        z-index: 1;
    }}
    .block-container {{
        max-width: 900px;
        padding-top: 1.2rem;
        padding-left: clamp(0.8rem, 4vw, 2rem);
        padding-right: clamp(0.8rem, 4vw, 2rem);
    }}

    .cd-header {{
        background: linear-gradient(135deg, {GREEN} 0%, #045C29 100%);
        border-radius: 16px;
        padding: clamp(18px, 4vw, 28px);
        margin-bottom: 18px;
        color: white;
        position: relative;
        overflow: hidden;
        text-align: center;
        box-shadow: 0 6px 24px rgba(0, 66, 37, 0.25);
    }}
    .cd-header::after {{
        content: "";
        position: absolute;
        left: 0; right: 0; bottom: 0;
        height: 6px;
        background: linear-gradient(90deg, {GREEN} 0 33%, {RED} 33% 66%, {GOLD} 66% 100%);
    }}
    .cd-header.cd-header-compact {{
        padding: clamp(14px, 3vw, 20px);
    }}
    .cd-emblem {{
        width: clamp(48px, 10vw, 64px);
        height: auto;
        margin: 0 auto 8px auto;
        display: block;
        filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));
    }}
    .cd-eyebrow {{
        text-transform: uppercase;
        letter-spacing: 0.12em;
        font-size: clamp(0.62rem, 2vw, 0.72rem);
        opacity: 0.85;
        margin: 0 0 4px 0;
        font-weight: 600;
    }}
    .cd-header h1 {{
        margin: 0 0 8px 0;
        font-size: clamp(1.15rem, 4vw, 1.5rem);
        font-weight: 800;
        line-height: 1.25;
    }}
    .cd-header p {{
        margin: 0 auto;
        max-width: 560px;
        opacity: 0.92;
        font-size: clamp(0.8rem, 2.3vw, 0.92rem);
        line-height: 1.5;
    }}
    .cd-motto {{
        margin-top: 12px;
        font-size: clamp(0.6rem, 1.8vw, 0.7rem);
        letter-spacing: 0.15em;
        text-transform: uppercase;
        opacity: 0.75;
    }}
    .cd-star {{
        color: {GOLD};
    }}

    .cd-card {{
        background: rgba(255, 255, 255, 0.96);
        backdrop-filter: blur(2px);
        border: 1px solid #E7E5DE;
        border-radius: 14px;
        padding: clamp(16px, 3vw, 24px);
        margin-bottom: 20px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    }}

    .cd-result-badge {{
        display: inline-block;
        background: {GREEN};
        color: white;
        font-weight: 700;
        padding: 6px 16px;
        border-radius: 999px;
        font-size: 0.95rem;
        margin-bottom: 4px;
    }}
    .cd-confidence {{
        display: inline-block;
        background: {GOLD};
        color: {INK};
        font-weight: 700;
        padding: 6px 14px;
        border-radius: 999px;
        font-size: 0.85rem;
        margin-left: 8px;
    }}

    .cd-field-row {{
        display: flex;
        justify-content: space-between;
        gap: 12px;
        padding: 10px 4px;
        border-bottom: 1px solid #F0EFE9;
        font-size: 0.95rem;
    }}
    .cd-field-row:last-child {{ border-bottom: none; }}
    .cd-field-label {{
        color: #5B5F58;
        font-weight: 600;
    }}
    .cd-field-value {{
        color: {INK};
        font-weight: 600;
        text-align: right;
        word-break: break-word;
    }}
    .cd-field-missing {{
        color: #B0AEA5;
        font-style: italic;
        font-weight: 400;
    }}

    .cd-alert {{
        background: #FDECEC;
        border-left: 4px solid {RED};
        border-radius: 6px;
        padding: 10px 14px;
        margin: 6px 0;
        font-size: 0.9rem;
        color: #7A1420;
    }}
    .cd-success {{
        background: #E9F6EE;
        border-left: 4px solid {GREEN};
        border-radius: 6px;
        padding: 10px 14px;
        margin: 6px 0;
        font-size: 0.9rem;
        color: #0A4A24;
    }}
    .cd-info {{
        background: #FFF8E1;
        border-left: 4px solid {GOLD};
        border-radius: 6px;
        padding: 10px 14px;
        margin: 6px 0;
        font-size: 0.9rem;
        color: #6B5A00;
    }}

    .cd-footer {{
        text-align: center;
        color: #8A887F;
        font-size: 0.82rem;
        margin-top: 24px;
        padding-top: 16px;
        border-top: 1px solid #E7E5DE;
    }}

    .cd-feed-item {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 10px;
        padding: 12px 4px;
        border-bottom: 1px solid #F0EFE9;
    }}
    .cd-feed-item:last-child {{ border-bottom: none; }}
    .cd-feed-title {{
        font-weight: 700;
        color: {INK};
        font-size: 0.98rem;
    }}
    .cd-feed-sub {{
        color: #5B5F58;
        font-size: 0.82rem;
        margin-top: 2px;
    }}
    .cd-chip {{
        display: inline-block;
        background: #F0EFE9;
        color: #5B5F58;
        font-size: 0.72rem;
        font-weight: 700;
        padding: 3px 10px;
        border-radius: 999px;
        margin-top: 2px;
    }}

    .cd-profile-row {{
        display: flex;
        justify-content: space-between;
        padding: 12px 4px;
        border-bottom: 1px solid #F0EFE9;
        font-size: 0.95rem;
    }}
    .cd-profile-row:last-child {{ border-bottom: none; }}

    div[data-testid="stFileUploader"] section {{
        border: 2px dashed {GREEN}55;
        border-radius: 10px;
        background: #F5FAF6;
    }}
    .stButton>button {{
        background-color: {GREEN};
        color: white;
        border-radius: 8px;
        border: none;
        font-weight: 600;
    }}
    .stButton>button:hover {{
        background-color: #045C29;
        color: white;
    }}
    .stButton>button[kind="secondary"] {{
        background-color: white;
        color: {GREEN};
        border: 1.5px solid {GREEN};
    }}

    /* Colonnes résultat/photo : passent en pile verticale sur petit écran */
    @media (max-width: 640px) {{
        div[data-testid="column"] {{
            width: 100% !important;
            flex: 1 1 100% !important;
        }}
    }}
    </style>

    <img class="cd-watermark" src="{EMBLEM_DATA_URI}" alt="" />
    """,
    unsafe_allow_html=True,
)

DOC_ICONS = {
    "Carte Nationale d'Identité": "🪪",
    "Récépissé de CNI": "📃",
    "Passeport": "🛂",
    "Acte de naissance": "📜",
    "Diplôme": "🎓",
    "Permis de conduire": "🚗",
}

DOC_LABELS = {code: info["label"] for code, info in DOCUMENT_TYPES.items()}
LABEL_TO_CODE = {label: code for code, label in DOC_LABELS.items()}


def render_header(title: str, subtitle: str = "", compact: bool = False):
    # Important : tout tenir sur UNE SEULE ligne (pas de f-string multi-lignes
    # indentée). Un bloc HTML markdown multi-lignes indenté peut, selon son
    # contenu (ex. une ligne vide quand `subtitle` est vide), se faire couper
    # par le parseur Markdown de Streamlit en cours de route et retomber en
    # bloc de code littéral au lieu de HTML rendu — voir EMBLEM_SVG_INLINE
    # ci-dessus pour le même problème déjà rencontré sur le SVG.
    compact_class = " cd-header-compact" if compact else ""
    subtitle_html = f"<p>{subtitle}</p>" if subtitle else ""
    emblem_html = EMBLEM_SVG_INLINE.replace('<svg ', '<svg class="cd-emblem" ')
    header_html = (
        f'<div class="cd-header{compact_class}">'
        f'<div class="cd-eyebrow">République du Cameroun</div>'
        f'{emblem_html}'
        f'<h1>{title} <span class="cd-star">★</span></h1>'
        f'{subtitle_html}'
        f'<div class="cd-motto">Paix &nbsp;•&nbsp; Travail &nbsp;•&nbsp; Patrie</div>'
        f'</div>'
    )
    st.markdown(header_html, unsafe_allow_html=True)


def render_footer():
    st.markdown(
        '<div class="cd-footer">Findici — Prototype de test — l\'extraction dépend '
        "fortement de la qualité de la photo (cadrage, lumière, netteté, absence de reflets).</div>",
        unsafe_allow_html=True,
    )


def goto(screen: str):
    st.session_state.screen = screen
    st.rerun()


# ---------------------------------------------------------------------------
# État de session
# ---------------------------------------------------------------------------
st.session_state.setdefault("user", None)
st.session_state.setdefault("screen", "login")
st.session_state.setdefault("auth_mode", "login")
st.session_state.setdefault("detail_id", None)
st.session_state.setdefault("lost_autofill", None)


NAV_ITEMS = [
    ("accueil", "🏠", "Accueil"),
    ("declarer_perdu", "📢", "Déclarer perdu"),
    ("declarer_trouve", "🔍", "Déclarer trouvé"),
    ("mes", "🗂️", "Mes déclarations"),
    ("profil", "👤", "Profil"),
]

ADMIN_NAV_ITEM = ("admin", "🛡️", "Admin")


def render_nav():
    user = st.session_state.user
    items = list(NAV_ITEMS)
    if user and user.get("is_admin"):
        items.append(ADMIN_NAV_ITEM)
    cols = st.columns(len(items))
    current = st.session_state.screen
    for col, (screen_key, icon, label) in zip(cols, items):
        with col:
            btn_type = "primary" if current == screen_key else "secondary"
            if st.button(f"{icon}\n{label}", key=f"nav_{screen_key}", use_container_width=True, type=btn_type):
                if screen_key != current:
                    goto(screen_key)
    st.markdown("<div style='margin-bottom:8px;'></div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Écran : connexion / création de compte
# ---------------------------------------------------------------------------
def screen_login():
    render_header(
        "Findici",
        "La plateforme camerounaise de déclaration et de restitution des "
        "documents administratifs perdus ou retrouvés.",
    )

    st.markdown('<div class="cd-card">', unsafe_allow_html=True)
    mode = st.session_state.auth_mode
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Se connecter", use_container_width=True, type="primary" if mode == "login" else "secondary"):
            st.session_state.auth_mode = "login"
            st.rerun()
    with col_b:
        if st.button("Créer un compte", use_container_width=True, type="primary" if mode == "signup" else "secondary"):
            st.session_state.auth_mode = "signup"
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.auth_mode == "login":
        st.markdown('<div class="cd-card">', unsafe_allow_html=True)
        st.markdown("##### Connexion")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Mot de passe", type="password", key="login_password")
        if st.button("Se connecter", type="primary", key="login_submit"):
            user = authenticate_user(email, password)
            if user:
                st.session_state.user = user
                goto("accueil")
            else:
                st.markdown(
                    '<div class="cd-alert">Email ou mot de passe incorrect.</div>',
                    unsafe_allow_html=True,
                )
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown('<div class="cd-card">', unsafe_allow_html=True)
        st.markdown("##### Créer un compte")
        nom = st.text_input("Nom complet", key="signup_nom")
        email = st.text_input("Email", key="signup_email")
        telephone = st.text_input("Téléphone", key="signup_telephone")
        password = st.text_input("Mot de passe (6 caractères minimum)", type="password", key="signup_password")
        password_confirm = st.text_input("Confirmer le mot de passe", type="password", key="signup_password_confirm")
        if st.button("Créer mon compte", type="primary", key="signup_submit"):
            if password != password_confirm:
                st.markdown(
                    '<div class="cd-alert">Les deux mots de passe ne correspondent pas.</div>',
                    unsafe_allow_html=True,
                )
            else:
                try:
                    user_id = create_user(nom, email, password, telephone)
                    st.session_state.user = get_user(user_id)
                    send_notification(
                        "Findici — Nouveau compte créé",
                        f"Nom : {nom.strip()}\n"
                        f"Email : {email.strip().lower()}\n"
                        f"Téléphone : {telephone.strip() or 'non renseigné'}\n"
                        f"Date : {datetime.now().isoformat(timespec='seconds')}",
                    )
                    goto("accueil")
                except ValueError as e:
                    st.markdown(f'<div class="cd-alert">{e}</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    render_footer()


# ---------------------------------------------------------------------------
# Écran : accueil (fil des documents retrouvés)
# ---------------------------------------------------------------------------
def screen_accueil():
    render_header("Findici", compact=True)
    render_nav()

    st.markdown('<div class="cd-card">', unsafe_allow_html=True)
    st.markdown("##### 📋 Documents retrouvés récemment")
    query = st.text_input(
        "Rechercher (nom, type de document...)",
        key="feed_search",
        placeholder="Ex. : NGONO, passeport...",
    )
    st.markdown("</div>", unsafe_allow_html=True)

    documents = list_found_documents()
    if query.strip():
        q = query.strip().lower()
        documents = [
            d for d in documents
            if q in (d["fields"].get("nom") or "").lower()
            or q in DOC_LABELS.get(d["type_document"], "").lower()
        ]

    st.markdown('<div class="cd-card">', unsafe_allow_html=True)
    if not documents:
        st.markdown(
            '<p style="text-align:center; color:#8A887F;">Aucun document trouvé pour l\'instant.</p>',
            unsafe_allow_html=True,
        )
    for doc in documents:
        label = DOC_LABELS.get(doc["type_document"], doc["type_document"])
        icon = DOC_ICONS.get(label, "📄")
        nom = doc["fields"].get("nom") or "Nom non renseigné"
        col_info, col_btn = st.columns([3, 1])
        with col_info:
            st.markdown(
                f'<div class="cd-feed-item" style="border-bottom:none; padding-bottom:0;">'
                f'<div><div class="cd-feed-title">{icon} {nom}</div>'
                f'<div class="cd-feed-sub">Retrouvé le {doc["created_at"]}</div>'
                f'<span class="cd-chip">{label}</span></div></div>',
                unsafe_allow_html=True,
            )
        with col_btn:
            if st.button("Voir", key=f"feed_view_{doc['id']}", use_container_width=True):
                st.session_state.detail_id = doc["id"]
                goto("detail")
        st.markdown('<hr style="margin:4px 0; border-color:#F0EFE9;">', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    render_footer()


# ---------------------------------------------------------------------------
# Écran : déclarer un document perdu (avec pré-remplissage optionnel via
# une ancienne photo, et rapprochement automatique avec les documents déjà
# retrouvés).
# ---------------------------------------------------------------------------
def screen_declarer_perdu():
    render_header("Déclarer un document perdu", compact=True)
    render_nav()

    st.markdown('<div class="cd-card">', unsafe_allow_html=True)
    st.markdown("##### 🖼️ Vous avez une ancienne photo (ou un PDF) de ce document ?")
    st.markdown(
        "Utilisez-la pour pré-remplir automatiquement le formulaire ci-dessous "
        "(elle n'est pas enregistrée comme document retrouvé)."
    )
    old_photo = st.file_uploader(
        "Photo ou PDF existant (optionnel)",
        type=["jpg", "jpeg", "png", "pdf"],
        key="lost_old_photo",
    )
    if old_photo is not None and st.button("Analyser cette photo", key="analyze_old_photo"):
        tmp_path = save_uploaded_to_tmp(old_photo)
        try:
            with st.spinner("Analyse en cours..."):
                analysis = analyze_document(tmp_path)
            st.session_state.lost_autofill = analysis
            st.markdown(
                '<div class="cd-success">✅ Photo analysée : le formulaire ci-dessous a été pré-rempli.</div>',
                unsafe_allow_html=True,
            )
        except Exception as e:
            st.markdown(f'<div class="cd-alert">Erreur pendant l\'analyse : {e}</div>', unsafe_allow_html=True)
        finally:
            os.unlink(tmp_path)
    st.markdown("</div>", unsafe_allow_html=True)

    autofill = st.session_state.lost_autofill
    autofill_champs = autofill["champs"] if autofill else {}
    default_label = DOC_LABELS.get(autofill_champs.get("type_document"), None) if autofill else None

    st.markdown('<div class="cd-card">', unsafe_allow_html=True)
    st.markdown("##### 📢 Informations sur le document perdu")
    labels = list(DOC_LABELS.values())
    default_index = labels.index(default_label) if default_label in labels else 0
    chosen_label = st.selectbox("Type de document perdu", labels, index=default_index, key="decl_doc_type")
    doc_code = LABEL_TO_CODE[chosen_label]

    st.markdown("**Informations connues sur le document** _(au moins le nom, idéalement aussi un numéro)_")
    declared_fields = {}
    for field_key in DECLARATION_FIELDS.get(doc_code, ["nom"]):
        default_value = autofill_champs.get(field_key, "") or ""
        declared_fields[field_key] = st.text_input(
            FIELD_LABELS.get(field_key, field_key),
            value=default_value,
            key=f"decl_field_{doc_code}_{field_key}",
        )

    col_lieu, col_date = st.columns(2)
    with col_lieu:
        lieu_perte = st.text_input("Lieu de la perte (ville, quartier...)", key="decl_lieu")
    with col_date:
        date_perte = st.date_input("Date approximative de la perte", key="decl_date")

    st.markdown("**Vos coordonnées** _(pour être recontacté·e si le document est retrouvé)_")
    user = st.session_state.user
    contact_nom = st.text_input("Votre nom", value=user["nom"] if user else "", key="decl_contact_nom")
    col_tel, col_email = st.columns(2)
    with col_tel:
        contact_tel = st.text_input("Téléphone", value=(user or {}).get("telephone", "") or "", key="decl_contact_tel")
    with col_email:
        contact_email = st.text_input("Email", value=user["email"] if user else "", key="decl_contact_email")

    if st.button("Enregistrer ma déclaration", type="primary", key="decl_submit"):
        cleaned_fields = {k: v.strip() for k, v in declared_fields.items() if v and v.strip()}
        if not cleaned_fields:
            st.markdown(
                '<div class="cd-alert">Veuillez renseigner au moins une information sur le document (idéalement le nom).</div>',
                unsafe_allow_html=True,
            )
        elif not contact_tel.strip() and not contact_email.strip():
            st.markdown(
                '<div class="cd-alert">Merci d\'indiquer au moins un moyen de vous contacter (téléphone ou email).</div>',
                unsafe_allow_html=True,
            )
        else:
            fields_for_storage = {"type_document": doc_code, **cleaned_fields}
            decl_id = save_declaration(
                type_document=doc_code,
                fields=fields_for_storage,
                lieu_perte=lieu_perte.strip(),
                date_perte=str(date_perte),
                contact_nom=contact_nom.strip(),
                contact_telephone=contact_tel.strip(),
                contact_email=contact_email.strip(),
                user_id=user["id"] if user else None,
            )
            st.session_state.lost_autofill = None
            st.markdown(
                f'<div class="cd-success">✅ Déclaration n°{decl_id} enregistrée. '
                "Vous serez identifié·e automatiquement si un document correspondant est retrouvé.</div>",
                unsafe_allow_html=True,
            )
            send_notification(
                "Findici — Nouvelle déclaration de perte",
                f"Déclaration n°{decl_id}\n"
                f"Type : {DOC_LABELS.get(doc_code, doc_code)}\n"
                f"Champs connus : {cleaned_fields}\n"
                f"Lieu de la perte : {lieu_perte.strip() or 'non renseigné'}\n"
                f"Contact : {contact_nom.strip()} / {contact_tel.strip()} / {contact_email.strip()}",
            )

            document_matches = find_matching_documents(doc_code, fields_for_storage)
            if document_matches:
                st.markdown("##### 🎉 Bonne nouvelle : un document correspondant a déjà été retrouvé")
                for match in document_matches:
                    st.markdown(
                        f'<div class="cd-success">'
                        f"Document retrouvé le {match['created_at']} "
                        f"(correspondance sur « {match['matched_on']} ») — "
                        f"consultez l'écran « Accueil » pour voir les coordonnées de la personne qui l'a retrouvé."
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                    with st.expander(f"Détails du document retrouvé n°{match['id']}"):
                        st.json(match["fields"])

    st.markdown("</div>", unsafe_allow_html=True)
    render_footer()


# ---------------------------------------------------------------------------
# Écran : déclarer un document trouvé — détection automatique par photo, ou
# saisie manuelle en repli ("on ne sait jamais").
# ---------------------------------------------------------------------------
def screen_declarer_trouve():
    render_header("Déclarer un document trouvé", compact=True)
    render_nav()

    user = st.session_state.user
    mode = st.radio(
        "Comment voulez-vous procéder ?",
        ["📷 Détection automatique (photo)", "⌨️ Saisie manuelle"],
        key="trouve_mode",
        horizontal=True,
    )

    if mode.startswith("📷"):
        st.markdown('<div class="cd-card">', unsafe_allow_html=True)
        st.markdown("##### 📤 Choisis une photo ou un PDF de document")
        uploaded_file = st.file_uploader(
            "Formats acceptés : JPG, PNG, PDF",
            type=["jpg", "jpeg", "png", "pdf"],
            label_visibility="collapsed",
            key="trouve_photo",
        )
        finder_contact = st.text_input(
            "Votre numéro de téléphone (pour être contacté·e par le/la propriétaire)",
            value=(user or {}).get("telephone", "") or "",
            key="trouve_contact",
        )
        show_debug = st.checkbox("Afficher le texte brut lu par l'OCR (mode debug)", value=False, key="trouve_debug")
        st.markdown("</div>", unsafe_allow_html=True)

        if uploaded_file is not None:
            col1, col2 = st.columns([1, 1])
            uploaded_is_pdf = is_pdf_upload(uploaded_file.name)
            with col1:
                if uploaded_is_pdf:
                    st.markdown(
                        '<div class="cd-card" style="text-align:center; color:#5B5F58;">'
                        "📄 PDF envoyé — aperçu non disponible, mais l'analyse ci-contre "
                        "porte bien sur ce fichier.</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.image(uploaded_file, caption="Photo envoyée", use_container_width=True)

            tmp_path = save_uploaded_to_tmp(uploaded_file)

            result = None
            with st.spinner("Analyse en cours..."):
                try:
                    if show_debug:
                        from preprocessing import load_and_clean, get_aspect_ratio, is_blurry
                        from ocr import extract_text

                        debug_image_path = tmp_path
                        debug_converted_path = None
                        if uploaded_is_pdf:
                            debug_converted_path, _pages = pdf_first_page_to_image(tmp_path)
                            debug_image_path = debug_converted_path
                        try:
                            corrected_image, _ = load_and_clean(debug_image_path)
                            ratio = get_aspect_ratio(corrected_image)
                            blurry, sharpness = is_blurry(corrected_image)
                            raw = extract_text(corrected_image)
                            with st.expander("Détails techniques (debug)", expanded=True):
                                st.text(f"Ratio largeur/hauteur (après correction) : {ratio:.2f}")
                                st.text(f"Netteté (variance Laplacien) : {sharpness:.1f} {'-> FLOUE' if blurry else '-> nette'}")
                                st.image(
                                    cv2_to_rgb(corrected_image),
                                    caption="Image après correction de perspective / redressement",
                                    use_container_width=True,
                                )
                                st.text("Texte brut lu par l'OCR :")
                                st.text(raw if raw.strip() else "(rien lu par l'OCR)")
                        finally:
                            if debug_converted_path:
                                os.unlink(debug_converted_path)

                    result = process_document(
                        tmp_path,
                        debug=False,
                        user_id=user["id"] if user else None,
                        finder_contact=finder_contact.strip() or None,
                    )
                except Exception as e:
                    st.markdown(f'<div class="cd-alert">Erreur pendant le traitement : {e}</div>', unsafe_allow_html=True)
                finally:
                    os.unlink(tmp_path)

            if result:
                send_notification(
                    "Findici — Nouveau document trouvé",
                    f"Document n°{result['id']}\n"
                    f"Type : {result['type_document']}\n"
                    f"Confiance : {result['confidence']:.0%}\n"
                    f"Champs : {result['champs']}\n"
                    f"Contact du/de la trouveur·euse : {finder_contact.strip() or 'non renseigné'}",
                )
                with col2:
                    icon = DOC_ICONS.get(result["type_document"], "📄")
                    st.markdown('<div class="cd-card">', unsafe_allow_html=True)
                    st.markdown(
                        f'<div class="cd-result-badge">{icon} {result["type_document"]}</div>'
                        f'<span class="cd-confidence">Confiance : {result["confidence"]:.0%}</span>',
                        unsafe_allow_html=True,
                    )
                    rows_html = ""
                    for key, value in result["champs"].items():
                        if key == "type_document":
                            continue
                        if value in (None, "", []):
                            value_html = '<span class="cd-field-missing">non détecté</span>'
                        else:
                            value_html = str(value)
                        rows_html += (
                            f'<div class="cd-field-row">'
                            f'<span class="cd-field-label">{key.replace("_", " ").capitalize()}</span>'
                            f'<span class="cd-field-value">{value_html}</span>'
                            f"</div>"
                        )
                    st.markdown(f'<div style="margin-top:14px;">{rows_html}</div>', unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)

                if result["alertes"]:
                    for alert in result["alertes"]:
                        st.markdown(f'<div class="cd-alert">⚠️ {alert}</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="cd-success">✅ Informations enregistrées avec succès.</div>', unsafe_allow_html=True)

                declaration_matches = find_matching_declarations(
                    result["champs"]["type_document"], result["champs"]
                )
                if declaration_matches:
                    st.markdown("##### 📢 Correspond à une déclaration de perte")
                    for match in declaration_matches:
                        contact = match["contact_telephone"] or match["contact_email"] or "contact non renseigné"
                        st.markdown(
                            f'<div class="cd-success">'
                            f"Déclaration n°{match['id']} du {match['created_at']} "
                            f"(déclarant·e : {match['contact_nom'] or 'inconnu'}, "
                            f"correspondance sur « {match['matched_on']} ») — "
                            f"à recontacter : <strong>{contact}</strong>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

                with st.expander("Voir le JSON structuré"):
                    st.json(result["champs"])
        else:
            st.markdown(
                '<div class="cd-card" style="text-align:center; color:#8A887F;">'
                "En attente d'une photo…</div>",
                unsafe_allow_html=True,
            )

    else:
        st.markdown('<div class="cd-card">', unsafe_allow_html=True)
        st.markdown(
            "##### ⌨️ Saisie manuelle _(au cas où la détection automatique ne fonctionne pas — on ne sait jamais)_"
        )
        labels = list(DOC_LABELS.values())
        chosen_label = st.selectbox("Type de document trouvé", labels, key="manual_doc_type")
        doc_code = LABEL_TO_CODE[chosen_label]

        st.markdown("**Informations lues sur le document**")
        manual_fields = {}
        for field_key in DECLARATION_FIELDS.get(doc_code, ["nom"]):
            manual_fields[field_key] = st.text_input(
                FIELD_LABELS.get(field_key, field_key), key=f"manual_field_{doc_code}_{field_key}"
            )

        finder_contact = st.text_input(
            "Votre numéro de téléphone (pour être contacté·e par le/la propriétaire)",
            value=(user or {}).get("telephone", "") or "",
            key="manual_contact",
        )

        if st.button("Enregistrer ce document trouvé", type="primary", key="manual_submit"):
            cleaned_fields = {k: v.strip() for k, v in manual_fields.items() if v and v.strip()}
            if not cleaned_fields:
                st.markdown(
                    '<div class="cd-alert">Veuillez renseigner au moins une information sur le document.</div>',
                    unsafe_allow_html=True,
                )
            else:
                fields_for_storage = {"type_document": doc_code, **cleaned_fields}
                doc_id = save_document(
                    fields_for_storage,
                    confidence=1.0,
                    alerts=["Saisie manuelle — champs renseignés directement, pas d'OCR."],
                    source_image=None,
                    user_id=user["id"] if user else None,
                    finder_contact=finder_contact.strip() or None,
                )
                st.markdown(
                    f'<div class="cd-success">✅ Document n°{doc_id} enregistré manuellement.</div>',
                    unsafe_allow_html=True,
                )
                send_notification(
                    "Findici — Nouveau document trouvé (saisie manuelle)",
                    f"Document n°{doc_id}\n"
                    f"Type : {DOC_LABELS.get(doc_code, doc_code)}\n"
                    f"Champs : {cleaned_fields}\n"
                    f"Contact du/de la trouveur·euse : {finder_contact.strip() or 'non renseigné'}",
                )
                declaration_matches = find_matching_declarations(doc_code, fields_for_storage)
                if declaration_matches:
                    st.markdown("##### 📢 Correspond à une déclaration de perte")
                    for match in declaration_matches:
                        contact = match["contact_telephone"] or match["contact_email"] or "contact non renseigné"
                        st.markdown(
                            f'<div class="cd-success">'
                            f"Déclaration n°{match['id']} du {match['created_at']} "
                            f"(déclarant·e : {match['contact_nom'] or 'inconnu'}, "
                            f"correspondance sur « {match['matched_on']} ») — "
                            f"à recontacter : <strong>{contact}</strong>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
        st.markdown("</div>", unsafe_allow_html=True)

    render_footer()


# ---------------------------------------------------------------------------
# Écran : détail d'un document retrouvé (avec révélation des coordonnées).
# ---------------------------------------------------------------------------
def screen_detail():
    render_header("Détail du document", compact=True)
    if st.button("← Retour à l'accueil", key="detail_back"):
        goto("accueil")

    doc = get_document(st.session_state.detail_id) if st.session_state.detail_id else None
    if not doc:
        st.markdown('<div class="cd-alert">Document introuvable.</div>', unsafe_allow_html=True)
        render_footer()
        return

    label = DOC_LABELS.get(doc["type_document"], doc["type_document"])
    icon = DOC_ICONS.get(label, "📄")

    st.markdown('<div class="cd-card">', unsafe_allow_html=True)
    st.markdown(
        f'<div class="cd-result-badge">{icon} {label}</div>',
        unsafe_allow_html=True,
    )
    rows_html = ""
    for key, value in doc["fields"].items():
        if key == "type_document":
            continue
        if value in (None, "", []):
            value_html = '<span class="cd-field-missing">non détecté</span>'
        else:
            value_html = str(value)
        rows_html += (
            f'<div class="cd-field-row">'
            f'<span class="cd-field-label">{key.replace("_", " ").capitalize()}</span>'
            f'<span class="cd-field-value">{value_html}</span>'
            f"</div>"
        )
    st.markdown(f'<div style="margin-top:14px;">{rows_html}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="cd-feed-sub" style="margin-top:10px;">Retrouvé le {doc["created_at"]}</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="cd-card">', unsafe_allow_html=True)
    reveal_key = f"reveal_contact_{doc['id']}"
    st.session_state.setdefault(reveal_key, False)
    if not st.session_state[reveal_key]:
        st.markdown(
            "C'est votre document ? Révélez les coordonnées de la personne qui l'a retrouvé pour organiser la restitution."
        )
        if st.button("Voir les coordonnées", type="primary", key=f"reveal_btn_{doc['id']}"):
            st.session_state[reveal_key] = True
            st.rerun()
    else:
        contact = doc.get("finder_contact") or "Coordonnées non renseignées par la personne qui a retrouvé ce document."
        st.markdown(f'<div class="cd-success">📞 {contact}</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    render_footer()


# ---------------------------------------------------------------------------
# Écran : "Mes déclarations" — tableau de bord personnel (Perdus / Trouvés).
# ---------------------------------------------------------------------------
def screen_mes():
    render_header("Mes déclarations", compact=True)
    render_nav()

    user = st.session_state.user
    tab_perdus, tab_trouves = st.tabs(["📢 Perdus", "🔍 Trouvés"])

    with tab_perdus:
        declarations = list_user_declarations(user["id"]) if user else []
        if not declarations:
            st.markdown(
                '<div class="cd-card" style="text-align:center; color:#8A887F;">'
                "Vous n'avez pas encore fait de déclaration de perte.</div>",
                unsafe_allow_html=True,
            )
        for decl in declarations:
            label = DOC_LABELS.get(decl["type_document"], decl["type_document"])
            icon = DOC_ICONS.get(label, "📄")
            nom = decl["fields"].get("nom") or "Nom non renseigné"
            statut = "En attente" if decl["statut"] == "en_attente" else decl["statut"]
            st.markdown(
                f'<div class="cd-card"><div class="cd-feed-title">{icon} {nom}</div>'
                f'<div class="cd-feed-sub">Déclaré le {decl["created_at"]} — '
                f'Lieu : {decl.get("lieu_perte") or "non renseigné"}</div>'
                f'<span class="cd-chip">{label}</span>'
                f'<span class="cd-chip">{statut}</span></div>',
                unsafe_allow_html=True,
            )

    with tab_trouves:
        documents = list_user_documents(user["id"]) if user else []
        if not documents:
            st.markdown(
                '<div class="cd-card" style="text-align:center; color:#8A887F;">'
                "Vous n'avez pas encore enregistré de document trouvé.</div>",
                unsafe_allow_html=True,
            )
        for doc in documents:
            label = DOC_LABELS.get(doc["type_document"], doc["type_document"])
            icon = DOC_ICONS.get(label, "📄")
            nom = doc["fields"].get("nom") or "Nom non renseigné"
            col_info, col_btn = st.columns([3, 1])
            with col_info:
                st.markdown(
                    f'<div class="cd-card" style="margin-bottom:8px;">'
                    f'<div class="cd-feed-title">{icon} {nom}</div>'
                    f'<div class="cd-feed-sub">Retrouvé le {doc["created_at"]}</div>'
                    f'<span class="cd-chip">{label}</span></div>',
                    unsafe_allow_html=True,
                )
            with col_btn:
                if st.button("Voir", key=f"mes_view_{doc['id']}", use_container_width=True):
                    st.session_state.detail_id = doc["id"]
                    goto("detail")

    render_footer()


# ---------------------------------------------------------------------------
# Écran : profil.
# ---------------------------------------------------------------------------
def screen_profil():
    render_header("Mon profil", compact=True)
    render_nav()

    user = st.session_state.user
    st.markdown('<div class="cd-card">', unsafe_allow_html=True)
    st.markdown(
        f'<div class="cd-profile-row"><span>Nom</span><strong>{user["nom"]}</strong></div>'
        f'<div class="cd-profile-row"><span>Email</span><strong>{user["email"]}</strong></div>'
        f'<div class="cd-profile-row"><span>Téléphone</span>'
        f'<strong>{user.get("telephone") or "non renseigné"}</strong></div>',
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="cd-card">', unsafe_allow_html=True)
    st.markdown("##### 📥 Sauvegarde")
    st.markdown(
        "Cette application stocke ses données localement (fichier "
        "`documents.db`) : rien n'est automatiquement sauvegardé ailleurs. "
        "Télécharge régulièrement une copie de tous les documents, "
        "déclarations et comptes (hors mots de passe) au format JSON."
    )
    export_data = export_all_data()
    export_json = json.dumps(export_data, ensure_ascii=False, indent=2)
    export_filename = f"findici_sauvegarde_{datetime.now().strftime('%Y-%m-%d_%H%M')}.json"
    st.download_button(
        "Exporter mes données (JSON)",
        data=export_json,
        file_name=export_filename,
        mime="application/json",
        key="export_backup",
    )
    st.markdown(
        f'<p style="color:#5B5F58; font-size:0.85rem; margin-top:8px;">'
        f"{len(export_data['documents'])} document(s), "
        f"{len(export_data['declarations'])} déclaration(s), "
        f"{len(export_data['users'])} compte(s) au total dans la base.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    if st.button("Se déconnecter", key="logout"):
        st.session_state.user = None
        st.session_state.detail_id = None
        st.session_state.lost_autofill = None
        st.session_state.auth_mode = "login"
        goto("login")

    render_footer()


# ---------------------------------------------------------------------------
# Écran : administration (réservé aux comptes is_admin) — vue d'ensemble de
# tout ce qui se passe dans le système, tous utilisateurs confondus.
# ---------------------------------------------------------------------------
def screen_admin():
    render_header("Administration", compact=True)
    render_nav()

    user = st.session_state.user
    if not user or not user.get("is_admin"):
        st.markdown(
            '<div class="cd-alert">Accès réservé aux administrateurs.</div>',
            unsafe_allow_html=True,
        )
        render_footer()
        return

    stats = get_admin_stats()

    st.markdown('<div class="cd-card">', unsafe_allow_html=True)
    st.markdown("##### 📊 Vue d'ensemble")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Documents trouvés", stats["total_documents"])
    col2.metric("Déclarations", stats["total_declarations"])
    col3.metric("— dont en attente", stats["pending_declarations"])
    col4.metric("Comptes", stats["total_users"])
    st.markdown("</div>", unsafe_allow_html=True)

    col_docs, col_decls = st.columns(2)
    with col_docs:
        st.markdown('<div class="cd-card">', unsafe_allow_html=True)
        st.markdown("##### Documents par type")
        if stats["documents_by_type"]:
            for type_code, count in sorted(stats["documents_by_type"].items(), key=lambda kv: -kv[1]):
                label = DOC_LABELS.get(type_code, type_code)
                st.markdown(
                    f'<div class="cd-field-row"><span class="cd-field-label">{label}</span>'
                    f'<span class="cd-field-value">{count}</span></div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown('<p style="color:#8A887F;">Aucun document pour l\'instant.</p>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col_decls:
        st.markdown('<div class="cd-card">', unsafe_allow_html=True)
        st.markdown("##### Déclarations par type")
        if stats["declarations_by_type"]:
            for type_code, count in sorted(stats["declarations_by_type"].items(), key=lambda kv: -kv[1]):
                label = DOC_LABELS.get(type_code, type_code)
                st.markdown(
                    f'<div class="cd-field-row"><span class="cd-field-label">{label}</span>'
                    f'<span class="cd-field-value">{count}</span></div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown('<p style="color:#8A887F;">Aucune déclaration pour l\'instant.</p>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    tab_docs, tab_decls, tab_users = st.tabs(["📄 Tous les documents", "📢 Toutes les déclarations", "👥 Tous les comptes"])

    with tab_docs:
        for doc in list_found_documents(limit=500):
            label = DOC_LABELS.get(doc["type_document"], doc["type_document"])
            nom = doc["fields"].get("nom") or "Nom non renseigné"
            st.markdown(
                f'<div class="cd-field-row"><span class="cd-field-label">#{doc["id"]} · {label} · {nom}</span>'
                f'<span class="cd-field-value">{doc["created_at"]}</span></div>',
                unsafe_allow_html=True,
            )

    with tab_decls:
        for decl in list_all_declarations():
            label = DOC_LABELS.get(decl["type_document"], decl["type_document"])
            nom = decl["fields"].get("nom") or "Nom non renseigné"
            st.markdown(
                f'<div class="cd-field-row"><span class="cd-field-label">#{decl["id"]} · {label} · {nom} · {decl["statut"]}</span>'
                f'<span class="cd-field-value">{decl["created_at"]}</span></div>',
                unsafe_allow_html=True,
            )

    with tab_users:
        for u in list_all_users():
            role = "🛡️ admin" if u.get("is_admin") else "utilisateur"
            st.markdown(
                f'<div class="cd-field-row"><span class="cd-field-label">#{u["id"]} · {u["nom"]} · {u["email"]}</span>'
                f'<span class="cd-field-value">{role}</span></div>',
                unsafe_allow_html=True,
            )

    render_footer()


# ---------------------------------------------------------------------------
# Routeur
# ---------------------------------------------------------------------------
if st.session_state.user is None:
    screen_login()
else:
    screen = st.session_state.screen
    if screen == "detail" and st.session_state.detail_id is not None:
        screen_detail()
    elif screen == "declarer_perdu":
        screen_declarer_perdu()
    elif screen == "declarer_trouve":
        screen_declarer_trouve()
    elif screen == "mes":
        screen_mes()
    elif screen == "profil":
        screen_profil()
    elif screen == "admin" and st.session_state.user.get("is_admin"):
        screen_admin()
    else:
        screen_accueil()
