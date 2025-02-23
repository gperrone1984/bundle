import streamlit as st
import streamlit.components.v1 as components
import os
import requests
import pandas as pd
import shutil
import uuid
import time
from io import BytesIO
from PIL import Image, ImageChops

# ----- Create a unique session ID and corresponding base folder for the session -----
if "session_id" not in st.session_state:
    st.session_state["session_id"] = str(uuid.uuid4())
session_id = st.session_state["session_id"]
base_folder = f"bundle_images_{session_id}"

# ----- Automatic cleaning at app start: remove previous files in the session folder -----
def clear_old_data():
    if os.path.exists(base_folder):
        shutil.rmtree(base_folder)
    temp_zip = "bundle_images_temp.zip"
    if os.path.exists(temp_zip):
        os.remove(temp_zip)
    zip_path = f"bundle_images_{session_id}.zip"
    if os.path.exists(zip_path):
        os.remove(zip_path)
    if os.path.exists("missing_images.csv"):
        os.remove("missing_images.csv")
    if os.path.exists("bundle_list.csv"):
        os.remove("bundle_list.csv")

clear_old_data()  # Clean session-specific files at startup

# ---------------------- Helper Functions ----------------------
def download_image(product_code, extension):
    if product_code.startswith(('1', '0')):
        product_code = f"D{product_code}"
    url = f"https://cdn.shop-apotheke.com/images/{product_code}-p{extension}.jpg"
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        return response.content, url
    return None, None

def get_image_with_fallback(product_code):
    """
    Tries first extension "1", then "10". 
    If these are not found and if the user has selected a fallback (FR o DE),
    it then tries that extension.
    Returns a tuple (content, used_ext) or (None, None).
    """
    for ext in ["1", "10"]:
        content, _ = download_image(product_code, ext)
        if content:
            return content, ext
    fallback_ext = st.session_state.get("fallback_ext", None)
    if fallback_ext:
        content, _ = download_image(product_code, fallback_ext)
        if content:
            return content, fallback_ext
    return None, None

def trim(im):
    bg = Image.new(im.mode, im.size, (255, 255, 255))
    diff = ImageChops.difference(im, bg)
    bbox = diff.getbbox()
    if bbox:
        return im.crop(bbox)
    return im

def process_double_bundle_image(image, orientation="horizontal"):
    image = trim(image)
    width, height = image.size

    if orientation == "horizontal":
        merged_width = width * 2
        merged_height = height
        merged_image = Image.new("RGB", (merged_width, merged_height), (255, 255, 255))
        merged_image.paste(image, (0, 0))
        merged_image.paste(image, (width, 0))
    else:  # verticale
        merged_width = width
        merged_height = height * 2
        merged_image = Image.new("RGB", (merged_width, merged_height), (255, 255, 255))
        merged_image.paste(image, (0, 0))
        merged_image.paste(image, (0, height))
        
    scale_factor = min(1000 / merged_width, 1000 / merged_height)
    new_size = (int(merged_width * scale_factor), int(merged_height * scale_factor))
    resized_image = merged_image.resize(new_size, Image.LANCZOS)
    final_image = Image.new("RGB", (1000, 1000), (255, 255, 255))
    x_offset = (1000 - new_size[0]) // 2
    y_offset = (1000 - new_size[1]) // 2
    final_image.paste(resized_image, (x_offset, y_offset))
    return final_image

def process_triple_bundle_image(image, orientation="horizontal"):
    image = trim(image)
    width, height = image.size

    if orientation == "horizontal":
        merged_width = width * 3
        merged_height = height
        merged_image = Image.new("RGB", (merged_width, merged_height), (255, 255, 255))
        merged_image.paste(image, (0, 0))
        merged_image.paste(image, (width, 0))
        merged_image.paste(image, (width * 2, 0))
    else:  # verticale
        merged_width = width
        merged_height = height * 3
        merged_image = Image.new("RGB", (merged_width, merged_height), (255, 255, 255))
        merged_image.paste(image, (0, 0))
        merged_image.paste(image, (0, height))
        merged_image.paste(image, (0, height * 2))
        
    scale_factor = min(1000 / merged_width, 1000 / merged_height)
    new_size = (int(merged_width * scale_factor), int(merged_height * scale_factor))
    resized_image = merged_image.resize(new_size, Image.LANCZOS)
    final_image = Image.new("RGB", (1000, 1000), (255, 255, 255))
    x_offset = (1000 - new_size[0]) // 2
    y_offset = (1000 - new_size[1]) // 2
    final_image.paste(resized_image, (x_offset, y_offset))
    return final_image

def find_bundle_image(bundle_code):
    """
    Cerca ricorsivamente all'interno della cartella base un file immagine che inizi con il codice bundle.
    """
    for root, dirs, files in os.walk(base_folder):
        for file in files:
            if file.startswith(bundle_code) and file.endswith(".jpg"):
                return os.path.join(root, file)
    return None

# ---------------------- Main Processing Function ----------------------
def process_file(uploaded_file, progress_bar=None):
    uploaded_file.seek(0)
    data = pd.read_csv(uploaded_file, delimiter=';', dtype=str)
    
    required_columns = {'sku', 'pzns_in_set'}
    missing_columns = required_columns - set(data.columns)
    if missing_columns:
        st.error(f"Missing required columns: {', '.join(missing_columns)}")
        return None, None, None, None
    
    if data.empty:
        st.error("The CSV file is empty!")
        return None, None, None, None
    
    data = data[list(required_columns)]
    data.dropna(inplace=True)
    
    st.write(f"File loaded: {len(data)} bundles found.")
    os.makedirs(base_folder, exist_ok=True)
    
    mixed_sets_needed = False
    mixed_folder = os.path.join(base_folder, "mixed_sets")
    error_list = []      # List of tuples: (bundle_code, product_code)
    bundle_list = []     # Details: bundle code, pzns list, bundle type, cross-country flag
    
    total = len(data)
    for i, (_, row) in enumerate(data.iterrows()):
        bundle_code = row['sku'].strip()
        product_codes = [code.strip() for code in row['pzns_in_set'].strip().split(',')]
        num_products = len(product_codes)
        is_uniform = (len(set(product_codes)) == 1)
        bundle_type = f"bundle di {num_products}" if is_uniform else "mixed"
        bundle_cross_country = False
        
        if is_uniform:
            product_code = product_codes[0]
            image_data, used_ext = get_image_with_fallback(product_code)
            if used_ext in ["1-fr", "1-de"]:
                bundle_cross_country = True
            folder_name = os.path.join(base_folder, "cross-country") if bundle_cross_country else os.path.join(base_folder, f"bundle_{num_products}")
            os.makedirs(folder_name, exist_ok=True)
            if image_data:
                try:
                    img = Image.open(BytesIO(image_data))
                    if num_products == 2:
                        final_img = process_double_bundle_image(img, orientation=st.session_state.get("orientation", "horizontal"))
                    elif num_products == 3:
                        final_img = process_triple_bundle_image(img, orientation=st.session_state.get("orientation", "horizontal"))
                    else:
                        final_img = img
                    final_img.save(os.path.join(folder_name, f"{bundle_code}-h1.jpg"), "JPEG", quality=100)
                except Exception as e:
                    st.error(f"Error processing image for bundle {bundle_code}: {e}")
                    error_list.append((bundle_code, product_code))
            else:
                error_list.append((bundle_code, product_code))
        else:
            mixed_sets_needed = True
            bundle_folder = os.path.join(mixed_folder, bundle_code)
            os.makedirs(bundle_folder, exist_ok=True)
            for product_code in product_codes:
                image_data, used_ext = get_image_with_fallback(product_code)
                if used_ext in ["1-fr", "1-de"]:
                    bundle_cross_country = True
                if image_data:
                    if used_ext in ["1-fr", "1-de"]:
                        prod_folder = os.path.join(bundle_folder, "cross-country")
                        os.makedirs(prod_folder, exist_ok=True)
                    else:
                        prod_folder = bundle_folder
                    with open(os.path.join(prod_folder, f"{product_code}.jpg"), 'wb') as file:
                        file.write(image_data)
                else:
                    error_list.append((bundle_code, product_code))
        
        if progress_bar is not None:
            progress_bar.progress((i + 1) / total)
        
        bundle_list.append([bundle_code, ', '.join(product_codes), bundle_type, "Yes" if bundle_cross_country else "No"])
    
    if not mixed_sets_needed and os.path.exists(mixed_folder):
        shutil.rmtree(mixed_folder)
    
    if error_list:
        missing_images_df = pd.DataFrame(error_list, columns=["PZN Bundle", "PZN with image missing"])
        missing_images_df = missing_images_df.groupby("PZN Bundle", as_index=False).agg({
            "PZN with image missing": lambda x: ', '.join(x)
        })
    else:
        missing_images_df = pd.DataFrame(columns=["PZN Bundle", "PZN with image missing"])
    
    missing_images_csv = "missing_images.csv"
    missing_images_df.to_csv(missing_images_csv, index=False, sep=';')
    with open(missing_images_csv, "rb") as f:
        missing_images_data = f.read()
    
    bundle_list_df = pd.DataFrame(bundle_list, columns=["sku", "pzns_in_set", "bundle type", "cross-country"])
    bundle_list_csv = "bundle_list.csv"
    bundle_list_df.to_csv(bundle_list_csv, index=False, sep=';')
    with open(bundle_list_csv, "rb") as f:
        bundle_list_data = f.read()
    
    # Salva il dataframe dei bundle in sessione per l'anteprima
    st.session_state["bundle_list_df"] = bundle_list_df
    
    zip_path = f"bundle_images_{session_id}.zip"
    shutil.make_archive("bundle_images_temp", 'zip', base_folder)
    os.rename("bundle_images_temp.zip", zip_path)
    with open(zip_path, "rb") as zip_file:
        return zip_file.read(), missing_images_data, missing_images_df, bundle_list_data

# ---------------------- End of Function Definitions ----------------------

# Main UI
st.title("PDM Bundle Image Creator")

st.markdown("""
📌 **Istruzioni:**
1. Creare un **Quick Report** in Akeneo contenente la lista dei prodotti.
2. Selezionare le opzioni:
   - Tipo file: **CSV**
   - **All Attributes** o **Grid Context** (per Grid Context selezionare **ID** e **PZN included in the set**)
   - **With Codes**
   - **Without Media**
""")

# Clear Cache and Reset Data button
if st.button("🧹 Clear Cache and Reset Data"):
    st.session_state.clear()
    st.cache_data.clear()
    clear_old_data()
    components.html("<script>window.location.href=window.location.origin+window.location.pathname;</script>", height=0)

# Sidebar: Sezione per la preview dei codici dei bundle e scelta dell'orientamento
st.sidebar.header("🔎 Anteprima Bundle")
orientation_preview = st.sidebar.selectbox("Seleziona Orientamento:", ["horizontal", "vertical"])
# Salva l'orientamento scelto in sessione per essere usato anche in fase di processing
st.session_state["orientation"] = orientation_preview

if "bundle_list_df" in st.session_state and not st.session_state["bundle_list_df"].empty:
    bundle_codes = st.session_state["bundle_list_df"]["sku"].tolist()
    selected_bundle = st.sidebar.selectbox("Seleziona Bundle da visualizzare:", bundle_codes)
    if st.sidebar.button("Visualizza Anteprima Bundle"):
        # Cerca l'immagine del bundle selezionato
        preview_path = find_bundle_image(selected_bundle)
        if preview_path and os.path.exists(preview_path):
            preview_img = Image.open(preview_path)
            st.sidebar.image(preview_img, caption=f"Anteprima Bundle: {selected_bundle} ({orientation_preview})", use_column_width=True)
        else:
            st.sidebar.error("Nessuna immagine disponibile per questo bundle.")

# Sidebar: Preview prodotto singolo (già esistente)
st.sidebar.header("🔎 Anteprima Prodotto")
product_code = st.sidebar.text_input("Inserisci Codice Prodotto:")
selected_extension = st.sidebar.selectbox("Seleziona Estensione Immagine:", [str(i) for i in range(1, 19)], key="sidebar_ext")
with st.sidebar:
    col_button, col_spinner = st.columns([2, 1])
    show_image = col_button.button("Mostra Immagine")
    spinner_placeholder = col_spinner.empty()

if show_image and product_code:
    with spinner_placeholder:
        with st.spinner("Elaborazione in corso..."):
            image_data, image_url = download_image(product_code, selected_extension)
    if image_data:
        image = Image.open(BytesIO(image_data))
        st.sidebar.image(image, caption=f"Prodotto: {product_code} (p{selected_extension})", use_container_width=True)
        st.sidebar.download_button(
            label="📥 Scarica Immagine",
            data=image_data,
            file_name=f"{product_code}-p{selected_extension}.jpg",
            mime="image/jpeg"
        )
    else:
        st.sidebar.error(f"⚠️ Immagine non trovata per {product_code} con -p{selected_extension}.jpg")

# Main Content: File Uploader e processazione CSV
uploaded_file = st.file_uploader("Carica il file CSV", type=["csv"], key="file_uploader")
if uploaded_file:
    cols = st.columns([2, 1, 1, 1])
    with cols[0]:
        if st.button("Processa CSV"):
            start_time = time.time()  # Avvio timer
            progress_bar = st.progress(0)
            zip_data, missing_images_data, missing_images_df, bundle_list_data = process_file(uploaded_file, progress_bar)
            progress_bar.empty()
            elapsed_time = time.time() - start_time
            minutes = int(elapsed_time // 60)
            seconds = int(elapsed_time % 60)
            st.write(f"Tempo di elaborazione: {minutes} minuti e {seconds} secondi")
            if zip_data:
                st.session_state["zip_data"] = zip_data
                st.session_state["bundle_list_data"] = bundle_list_data
                st.session_state["missing_images_data"] = missing_images_data
    with cols[1]:
        st.markdown("**Foto cross-country:**")
    with cols[2]:
        if st.button("FR", key="fr_button_main"):
            st.session_state["fallback_ext"] = "1-fr"
    with cols[3]:
        if st.button("DE", key="de_button_main"):
            st.session_state["fallback_ext"] = "1-de"

if "zip_data" in st.session_state:
    st.success("**Elaborazione completata! Scarica i file qui sotto.**")
    st.download_button(
        label="🖼️ Scarica ZIP Bundle Images",
        data=st.session_state["zip_data"],
        file_name=f"bundle_images_{session_id}.zip",
        mime="application/zip"
    )
    st.download_button(
        label="📋 Scarica Lista Bundle",
        data=st.session_state["bundle_list_data"],
        file_name="bundle_list.csv",
        mime="text/csv"
    )
    if "missing_images_df" in st.session_state and not st.session_state["missing_images_df"].empty:
        st.warning("**Alcune immagini non sono state trovate:**")
        st.dataframe(st.session_state["missing_images_df"].reset_index(drop=True))
        st.download_button(
            label="⚠️ Scarica CSV Immagini Mancanti",
            data=st.session_state["missing_images_data"],
            file_name="missing_images.csv",
            mime="text/csv"
        )
