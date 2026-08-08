"""
Interface web (Streamlit) pour tester le pipeline de détection de documents
sans toucher au code : la personne ouvre un lien, dépose une photo, voit le
résultat. Déployé sur Streamlit Community Cloud — voir README.md.
"""

import os
import tempfile
import urllib.parse

import cv2
import streamlit as st

from main import process_document


def cv2_to_rgb(image):
    """Convertit une image OpenCV (BGR) en RGB pour l'affichage Streamlit."""
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


st.set_page_config(
    page_title="Détection de documents — Cameroun",
    page_icon="🇨🇲",
    layout="centered",
)

# ---------------------------------------------------------------------------
# Design : palette inspirée du drapeau camerounais
#   vert  #007A33   rouge  #CE1126   jaune/or  #FCD116
# ---------------------------------------------------------------------------
GREEN = "#007A33"
GREEN_DARK = "#00512199"
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
        padding-top: 1.6rem;
        padding-left: clamp(0.8rem, 4vw, 2rem);
        padding-right: clamp(0.8rem, 4vw, 2rem);
    }}

    .cd-header {{
        background: linear-gradient(135deg, {GREEN} 0%, #045C29 100%);
        border-radius: 16px;
        padding: clamp(20px, 4vw, 32px);
        margin-bottom: 28px;
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
    .cd-emblem {{
        width: clamp(56px, 12vw, 78px);
        height: auto;
        margin: 0 auto 10px auto;
        display: block;
        filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));
    }}
    .cd-eyebrow {{
        text-transform: uppercase;
        letter-spacing: 0.12em;
        font-size: clamp(0.65rem, 2vw, 0.75rem);
        opacity: 0.85;
        margin: 0 0 4px 0;
        font-weight: 600;
    }}
    .cd-header h1 {{
        margin: 0 0 10px 0;
        font-size: clamp(1.25rem, 4.2vw, 1.65rem);
        font-weight: 800;
        line-height: 1.25;
    }}
    .cd-header p {{
        margin: 0 auto;
        max-width: 560px;
        opacity: 0.92;
        font-size: clamp(0.82rem, 2.4vw, 0.95rem);
        line-height: 1.55;
    }}
    .cd-motto {{
        margin-top: 14px;
        font-size: clamp(0.62rem, 1.8vw, 0.72rem);
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

    .cd-footer {{
        text-align: center;
        color: #8A887F;
        font-size: 0.82rem;
        margin-top: 24px;
        padding-top: 16px;
        border-top: 1px solid #E7E5DE;
    }}

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

# ---------------------------------------------------------------------------
# En-tête
# ---------------------------------------------------------------------------
st.markdown(
    f"""
    <div class="cd-header">
        <div class="cd-eyebrow">République du Cameroun</div>
        {EMBLEM_SVG_INLINE.replace('<svg ', '<svg class="cd-emblem" ')}
        <h1>Détection automatique des documents <span class="cd-star">★</span></h1>
        <p>Système de gestion des objets perdus et retrouvés — dépose une photo de CNI,
        récépissé, passeport, acte de naissance, diplôme ou permis de conduire :
        le système l'identifie et en extrait les informations automatiquement.</p>
        <div class="cd-motto">Paix &nbsp;•&nbsp; Travail &nbsp;•&nbsp; Patrie</div>
    </div>
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

# ---------------------------------------------------------------------------
# Zone de dépôt
# ---------------------------------------------------------------------------
st.markdown('<div class="cd-card">', unsafe_allow_html=True)
st.markdown("##### 📤 Choisis une photo de document")
uploaded_file = st.file_uploader(
    "Formats acceptés : JPG, PNG",
    type=["jpg", "jpeg", "png"],
    label_visibility="collapsed",
)
show_debug = st.checkbox("Afficher le texte brut lu par l'OCR (mode debug)", value=False)
st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Traitement + résultats
# ---------------------------------------------------------------------------
if uploaded_file is not None:
    col1, col2 = st.columns([1, 1])
    with col1:
        st.image(uploaded_file, caption="Photo envoyée", use_container_width=True)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        tmp.write(uploaded_file.getbuffer())
        tmp_path = tmp.name

    result = None
    with st.spinner("Analyse en cours..."):
        try:
            if show_debug:
                from preprocessing import load_and_clean, get_aspect_ratio, is_blurry
                from ocr import extract_text

                corrected_image, _ = load_and_clean(tmp_path)
                ratio = get_aspect_ratio(corrected_image)
                blurry, sharpness = is_blurry(corrected_image)
                # OCR sur l'image déjà corrigée (perspective/redressement), pour
                # afficher exactement ce que le pipeline utilise réellement.
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

            result = process_document(tmp_path, debug=False)
        except Exception as e:
            st.markdown(f'<div class="cd-alert">Erreur pendant le traitement : {e}</div>', unsafe_allow_html=True)
        finally:
            os.unlink(tmp_path)

    if result:
        with col2:
            icon = DOC_ICONS.get(result["type_document"], "📄")
            st.markdown('<div class="cd-card">', unsafe_allow_html=True)
            st.markdown(
                f"""
                <div class="cd-result-badge">{icon} {result['type_document']}</div>
                <span class="cd-confidence">Confiance : {result['confidence']:.0%}</span>
                """,
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

        with st.expander("Voir le JSON structuré"):
            st.json(result["champs"])
else:
    st.markdown(
        '<div class="cd-card" style="text-align:center; color:#8A887F;">'
        "En attente d'une photo…</div>",
        unsafe_allow_html=True,
    )

st.markdown(
    """
    <div class="cd-footer">
        Prototype de test — l'extraction dépend fortement de la qualité de la photo
        (cadrage, lumière, netteté, absence de reflets).
    </div>
    """,
    unsafe_allow_html=True,
)