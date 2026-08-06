"""
Interface web simple (Streamlit) pour tester le pipeline de détection de
documents sans toucher au code.
"""

import os
import tempfile

import streamlit as st

from main import process_document

st.set_page_config(page_title="Détection de documents", page_icon="📄", layout="centered")

st.title("📄 Détection automatique des documents")
st.caption(
    "Système de gestion des objets perdus et retrouvés — prototype v1. "
    "Dépose une photo de CNI, récépissé, passeport, acte de naissance, diplôme "
    "ou permis de conduire, et laisse le système l'analyser."
)

uploaded_file = st.file_uploader("Choisis une photo de document", type=["jpg", "jpeg", "png"])
show_debug = st.checkbox("Afficher le texte brut lu par l'OCR (mode debug)", value=False)

if uploaded_file is not None:
    st.image(uploaded_file, caption="Photo envoyée", use_container_width=True)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        tmp.write(uploaded_file.getbuffer())
        tmp_path = tmp.name

    result = None
    with st.spinner("Analyse en cours..."):
        try:
            if show_debug:
                from preprocessing import load_and_clean, get_aspect_ratio
                from ocr import extract_text

                image, _ = load_and_clean(tmp_path)
                ratio = get_aspect_ratio(image)
                raw = extract_text(tmp_path)
                with st.expander("Texte brut OCR (debug)", expanded=True):
                    st.text(f"Ratio largeur/hauteur : {ratio:.2f}")
                    st.text(raw if raw.strip() else "(rien lu par l'OCR)")

            result = process_document(tmp_path, debug=False)
        except Exception as e:
            st.error(f"Erreur pendant le traitement : {e}")
        finally:
            os.unlink(tmp_path)

    if result:
        st.success(f"**{result['type_document']}** détecté — confiance : {result['confidence']:.0%}")

        st.subheader("Informations extraites")
        for key, value in result["champs"].items():
            if key == "type_document":
                continue
            display_value = value if value not in (None, "", []) else "_non détecté_"
            st.markdown(f"- **{key}** : {display_value}")

        if result["alertes"]:
            st.warning("Alertes de validation :")
            for alert in result["alertes"]:
                st.markdown(f"- {alert}")
        else:
            st.info("Informations enregistrées avec succès.")

        with st.expander("Voir le JSON structuré"):
            st.json(result["champs"])
else:
    st.info("En attente d'une photo...")

st.divider()
st.caption(
    "Prototype de test — l'extraction dépend fortement de la qualité de la photo "
    "(cadrage, lumière, netteté, absence de reflets)."
)