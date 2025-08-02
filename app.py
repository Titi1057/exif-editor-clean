import streamlit as st
from PIL import Image
import piexif
import io

def to_str(value):
    if isinstance(value, bytes):
        try:
            return value.decode('utf-8')
        except:
            return str(value)
    elif isinstance(value, tuple):
        # rationnel (num, den) ou tuple de rationnels
        try:
            if all(isinstance(x, tuple) and len(x) == 2 for x in value):
                # Liste de rationnels
                return ", ".join([f"{n}/{d}" for n, d in value])
            elif len(value) == 2 and all(isinstance(x, int) for x in value):
                # Un rationnel simple
                n, d = value
                return f"{n}/{d}"
            else:
                return str(value)
        except:
            return str(value)
    else:
        return str(value)

def from_str(value, original):
    # Convertir chaîne texte en type EXIF approprié
    try:
        if isinstance(original, bytes):
            return value.encode('utf-8')
        elif isinstance(original, tuple):
            # rationnel(s)
            parts = value.split(',')
            rationals = []
            for part in parts:
                part = part.strip()
                if '/' in part:
                    n, d = part.split('/')
                    rationals.append( (int(n), int(d)) )
                else:
                    # si pas rationnel, on fait 1/d
                    rationals.append( (int(part), 1) )
            if len(rationals) == 1:
                return rationals[0]
            else:
                return tuple(rationals)
        elif isinstance(original, int):
            return int(value)
        else:
            return value
    except:
        # fallback
        return value

st.set_page_config(page_title="Éditeur EXIF complet", layout="centered")

st.title("🖼️ Éditeur complet des métadonnées EXIF")

uploaded_file = st.file_uploader("Choisissez une image JPEG", type=["jpg", "jpeg"])

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="Image sélectionnée", use_column_width=True)
    img_bytes = uploaded_file.getvalue()

    try:
        exif_dict = piexif.load(img_bytes)
    except Exception as e:
        st.error(f"Erreur lors du chargement des métadonnées EXIF: {e}")
        st.stop()

    st.subheader("📝 Formulaire de modification EXIF")

    with st.form("exif_form"):
        new_exif = {}

        for ifd in exif_dict:
            if ifd == "thumbnail":
                continue
            st.markdown(f"### Section {ifd}")
            new_exif[ifd] = {}

            for tag, value in exif_dict[ifd].items():
                tag_name = piexif.TAGS[ifd][tag]["name"]
                val_str = to_str(value)
                new_val = st.text_input(f"{tag_name} ({ifd})", val_str)
                new_exif[ifd][tag] = (new_val, value)  # on stocke l’input et la valeur originale pour conversion

        submitted = st.form_submit_button("💾 Enregistrer les modifications")

    if submitted:
        # Mise à jour des exif_dict avec conversion de types
        for ifd in new_exif:
            for tag in new_exif[ifd]:
                user_val_str, original_val = new_exif[ifd][tag]
                exif_dict[ifd][tag] = from_str(user_val_str, original_val)

        # Générer les bytes EXIF et sauvegarder en mémoire
        try:
            exif_bytes = piexif.dump(exif_dict)
        except Exception as e:
            st.error(f"Erreur lors de la création des métadonnées modifiées: {e}")
            st.stop()

        output_buffer = io.BytesIO()
        image.save(output_buffer, format="JPEG", exif=exif_bytes)

        st.success("✅ Métadonnées mises à jour avec succès !")

        st.download_button(
            label="⬇️ Télécharger l'image modifiée avec EXIF",
            data=output_buffer.getvalue(),
            file_name="image_modifiee.jpg",
            mime="image/jpeg"
        )
