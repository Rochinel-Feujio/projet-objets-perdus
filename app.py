"""
Interface web (Streamlit) pour tester le pipeline de détection de documents
sans toucher au code : la personne ouvre un lien, dépose une photo, voit le
résultat. Déployé sur Streamlit Community Cloud — voir README.md.
"""

import os
import tempfile

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

st.markdown(
    f"""
    <style>
    .stApp {{
        background-color: #FAFAF8;
    }}
    #MainMenu, footer {{visibility: hidden;}}

    .cd-header {{
        background: linear-gradient(135deg, {GREEN} 0%, #045C29 100%);
        border-radius: 14px;
        padding: 28px 32px;
        margin-bottom: 28px;
        color: white;
        position: relative;
        overflow: hidden;
    }}
    .cd-header::after {{
        content: "";
        position: absolute;
        left: 0; right: 0; bottom: 0;
        height: 6px;
        background: linear-gradient(90deg, {GREEN} 0 33%, {RED} 33% 66%, {GOLD} 66% 100%);
    }}
    .cd-header h1 {{
        margin: 0 0 6px 0;
        font-size: 1.7rem;
        font-weight: 800;
        display: flex;
        align-items: center;
        gap: 10px;
    }}
    .cd-header p {{
        margin: 0;
        opacity: 0.92;
        font-size: 0.95rem;
        line-height: 1.5;
    }}
    .cd-star {{
        color: {GOLD};
    }}

    .cd-card {{
        background: white;
        border: 1px solid #E7E5DE;
        border-radius: 12px;
        padding: 22px 24px;
        margin-bottom: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
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
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# En-tête
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="cd-header">
        <h1>🪪 Détection automatique des documents <span class="cd-star">★</span></h1>
        <p>Système de gestion des objets perdus et retrouvés — République du Cameroun<br>
        Dépose une photo de CNI, récépissé, passeport, acte de naissance, diplôme ou
        permis de conduire : le système l'identifie et en extrait les informations automatiquement.</p>
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