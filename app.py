import streamlit as st
from PIL import Image
import piexif
import io
import folium
from streamlit_folium import st_folium

# --- Fonctions utilitaires pour EXIF ---
def to_str(value):
    if isinstance(value, bytes):
        try:
            return value.decode('utf-8')
        except:
            return str(value)
    elif isinstance(value, tuple):
        try:
            if all(isinstance(x, tuple) and len(x) == 2 for x in value):
                return ", ".join([f"{n}/{d}" for n, d in value])
            elif len(value) == 2 and all(isinstance(x, int) for x in value):
                n, d = value
                return f"{n}/{d}"
            else:
                return str(value)
        except:
            return str(value)
    else:
        return str(value)

def from_str(value, original):
    try:
        if isinstance(original, bytes):
            return value.encode('utf-8')
        elif isinstance(original, tuple):
            parts = value.split(',')
            rationals = []
            for part in parts:
                part = part.strip()
                if '/' in part:
                    n, d = part.split('/')
                    rationals.append((int(n), int(d)))
                else:
                    rationals.append((int(part), 1))
            if len(rationals) == 1:
                return rationals[0]
            else:
                return tuple(rationals)
        elif isinstance(original, int):
            return int(value)
        else:
            return value
    except:
        return value

def to_rational(number):
    precision = 1000000
    numerator = int(number * precision)
    denominator = precision
    return (numerator, denominator)

def decimal_to_dms(decimal_coord):
    degrees = int(abs(decimal_coord))
    minutes = int((abs(decimal_coord) - degrees) * 60)
    seconds = (abs(decimal_coord) - degrees - minutes / 60) * 3600
    return (
        to_rational(degrees),
        to_rational(minutes),
        to_rational(seconds)
    )

def gps_ref(latitude, longitude):
    lat_ref = 'N' if latitude >= 0 else 'S'
    lon_ref = 'E' if longitude >= 0 else 'W'
    return lat_ref.encode(), lon_ref.encode()

def set_gps_coords(exif_dict, lat, lon):
    exif_dict['GPS'][piexif.GPSIFD.GPSLatitudeRef] = gps_ref(lat, lon)[0]
    exif_dict['GPS'][piexif.GPSIFD.GPSLatitude] = decimal_to_dms(lat)
    exif_dict['GPS'][piexif.GPSIFD.GPSLongitudeRef] = gps_ref(lat, lon)[1]
    exif_dict['GPS'][piexif.GPSIFD.GPSLongitude] = decimal_to_dms(lon)
    return exif_dict

def get_gps_coord(exif_dict, key_ref, key_coord):
    try:
        ref = exif_dict['GPS'][key_ref].decode()
        d, m, s = exif_dict['GPS'][key_coord]
        coord = d[0] / d[1] + m[0] / (60 * m[1]) + s[0] / (3600 * s[1])
        if ref in ['S', 'W']:
            coord = -coord
        return coord
    except:
        return 0.0

# --- Interface Streamlit ---

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

    if 'GPS' not in exif_dict:
        exif_dict['GPS'] = {}

    # Initialisation session_state lat/lon s'ils n'existent pas
    if 'lat' not in st.session_state:
        st.session_state.lat = get_gps_coord(exif_dict, piexif.GPSIFD.GPSLatitudeRef, piexif.GPSIFD.GPSLatitude)
    if 'lon' not in st.session_state:
        st.session_state.lon = get_gps_coord(exif_dict, piexif.GPSIFD.GPSLongitudeRef, piexif.GPSIFD.GPSLongitude)

    st.subheader("📝 Formulaire de modification EXIF")

    with st.form("exif_form"):
        new_exif = {}
        for ifd in exif_dict:
            if ifd == "thumbnail":
                continue
            new_exif[ifd] = {}

            for tag, value in exif_dict[ifd].items():
                if ifd == "GPS" and tag in (
                    piexif.GPSIFD.GPSLatitude,
                    piexif.GPSIFD.GPSLongitude,
                    piexif.GPSIFD.GPSLatitudeRef,
                    piexif.GPSIFD.GPSLongitudeRef,
                ):
                    continue
                tag_name = piexif.TAGS[ifd][tag]["name"]
                val_str = to_str(value)
                new_val = st.text_input(f"{tag_name} ({ifd})", val_str)
                new_exif[ifd][tag] = (new_val, value)

        # Inputs GPS liés au session_state
        lat = st.number_input("Latitude (décimale)", value=st.session_state.lat)
        lon = st.number_input("Longitude (décimale)", value=st.session_state.lon)

        submitted = st.form_submit_button("💾 Enregistrer les modifications")

    if submitted:
        for ifd in new_exif:
            for tag in new_exif[ifd]:
                user_val_str, original_val = new_exif[ifd][tag]
                exif_dict[ifd][tag] = from_str(user_val_str, original_val)

        # Met à jour exif_dict avec nouvelles coordonnées GPS
        exif_dict = set_gps_coords(exif_dict, lat, lon)

        # Met à jour session_state avec les nouvelles coordonnées
        st.session_state.lat = lat
        st.session_state.lon = lon

        try:
            exif_bytes = piexif.dump(exif_dict)
        except Exception as e:
            st.error(f"Erreur lors de la création des métadonnées modifiées: {e}")
            st.stop()

        output_buffer = io.BytesIO()
        image.save(output_buffer, format="JPEG", exif=exif_bytes)

        # Stocke le résultat dans session_state pour garder le bouton visible
        st.session_state['image_modifiee'] = output_buffer.getvalue()

        st.success("✅ Métadonnées mises à jour avec succès !")

    # Affiche toujours le bouton de téléchargement si image modifiée existe
    if 'image_modifiee' in st.session_state:
        st.download_button(
            label="⬇️ Télécharger l'image modifiée avec EXIF",
            data=st.session_state['image_modifiee'],
            file_name="image_modifiee.jpg",
            mime="image/jpeg"
        )

    # Affichage de la carte avec coordonnées en session_state
    if st.session_state.lat != 0.0 and st.session_state.lon != 0.0:
        m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=12)
        folium.Marker([st.session_state.lat, st.session_state.lon], tooltip="Position GPS modifiée").add_to(m)
        st.subheader("📍 Position GPS sur la carte")
        st_folium(m, width=700, height=500)
