import streamlit as st
from PIL import Image
import piexif
import io
import folium
from streamlit_folium import st_folium

# Fonction pour convertir décimal en rationnel EXIF (num, den)
def to_rational(number):
    precision = 1000000  # 6 décimales
    numerator = int(number * precision)
    denominator = precision
    return (numerator, denominator)

# Convertir coordonnées GPS décimales en format EXIF
def decimal_to_dms(decimal_coord):
    degrees = int(abs(decimal_coord))
    minutes = int((abs(decimal_coord) - degrees) * 60)
    seconds = (abs(decimal_coord) - degrees - minutes/60) * 3600
    return (
        to_rational(degrees),
        to_rational(minutes),
        to_rational(seconds)
    )

# Déterminer le tag de référence N/S ou E/W
def gps_ref(latitude, longitude):
    lat_ref = 'N' if latitude >= 0 else 'S'
    lon_ref = 'E' if longitude >= 0 else 'W'
    return lat_ref.encode(), lon_ref.encode()

# Ajout/modification des coordonnées GPS dans les EXIF
def set_gps_coords(exif_dict, lat, lon):
    exif_dict['GPS'][piexif.GPSIFD.GPSLatitudeRef] = gps_ref(lat, lon)[0]
    exif_dict['GPS'][piexif.GPSIFD.GPSLatitude] = decimal_to_dms(lat)
    exif_dict['GPS'][piexif.GPSIFD.GPSLongitudeRef] = gps_ref(lat, lon)[1]
    exif_dict['GPS'][piexif.GPSIFD.GPSLongitude] = decimal_to_dms(lon)
    return exif_dict

# Ton code existant, avec ajout de cette partie dans le formulaire :

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

    # Initialisation section GPS si absente
    if 'GPS' not in exif_dict:
        exif_dict['GPS'] = {}

    st.subheader("📝 Formulaire de modification EXIF")

    with st.form("exif_form"):
        new_exif = {}

        for ifd in exif_dict:
            if ifd == "thumbnail":
                continue
            st.markdown(f"### Section {ifd}")
            new_exif[ifd] = {}

            for tag, value in exif_dict[ifd].items():
                # On ne montre pas les tags GPS ici car on les modifie via un formulaire dédié
                if ifd == "GPS" and tag in (piexif.GPSIFD.GPSLatitude, piexif.GPSIFD.GPSLongitude,
                                            piexif.GPSIFD.GPSLatitudeRef, piexif.GPSIFD.GPSLongitudeRef):
                    continue
                tag_name = piexif.TAGS[ifd][tag]["name"]
                val_str = to_str(value)
                new_val = st.text_input(f"{tag_name} ({ifd})", val_str)
                new_exif[ifd][tag] = (new_val, value)

        st.markdown("### Modification des coordonnées GPS")
        # Récupérer valeurs GPS existantes si présentes, sinon 0
        def get_gps_coord(key_ref, key_coord):
            try:
                ref = exif_dict['GPS'][key_ref].decode()
                d, m, s = exif_dict['GPS'][key_coord]
                coord = d[0]/d[1] + m[0]/(60*m[1]) + s[0]/(3600*s[1])
                if ref in ['S', 'W']:
                    coord = -coord
                return coord
            except:
                return 0.0

        lat = st.number_input("Latitude (décimale)", value=get_gps_coord(piexif.GPSIFD.GPSLatitudeRef, piexif.GPSIFD.GPSLatitude))
        lon = st.number_input("Longitude (décimale)", value=get_gps_coord(piexif.GPSIFD.GPSLongitudeRef, piexif.GPSIFD.GPSLongitude))

        submitted = st.form_submit_button("💾 Enregistrer les modifications")

    if submitted:
        for ifd in new_exif:
            for tag in new_exif[ifd]:
                user_val_str, original_val = new_exif[ifd][tag]
                exif_dict[ifd][tag] = from_str(user_val_str, original_val)

        # Mettre à jour les coordonnées GPS
        exif_dict = set_gps_coords(exif_dict, lat, lon)

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

        # Affichage de la carte avec Folium
        if lat != 0.0 and lon != 0.0:
            m = folium.Map(location=[lat, lon], zoom_start=12)
            folium.Marker([lat, lon], tooltip="Position GPS modifiée").add_to(m)
            st.subheader("📍 Position GPS sur la carte")
            st_folium(m, width=700, height=500)
