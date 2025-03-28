import streamlit as st
import streamlit.components.v1 as components
import os
import aiohttp
import asyncio
import pandas as pd
import shutil
import uuid
import time
from io import BytesIO
from PIL import Image, ImageChops
from cryptography.fernet import Fernet

# ---------------------- Custom CSS ----------------------
# Imposta la larghezza massima della sidebar e migliora lo stile dei pulsanti
st.markdown(
    """
    <style>
    /* Imposta la larghezza massima della sidebar (l'utente può comunque ridimensionarla) */
    [data-testid="stSidebar"] > div:first-child {
        width: 550px;
    }
    /* Stile personalizzato per i pulsanti */
    .stButton > button {
        background-color: #706b9c;
        color: white;
        border: none;
        padding: 8px 16px;
        text-align: center;
        font-size: 16px;
        border-radius: 8px;
        cursor: pointer;
    }
    .stButton > button:hover {
        background-color: #625e8a;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ---------------------- Session State Management ----------------------
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "session_id" not in st.session_state:
    st.session_state["session_id"] = str(uuid.uuid4())

# ---------------------- Login ----------------------
if not st.session_state["authenticated"]:
    st.title("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username == "PDM_Team" and password == "bundlecreation":
            st.session_state["authenticated"] = True
            if hasattr(st, "experimental_rerun"):
                st.experimental_rerun()
            else:
                st.stop()
        else:
            st.error("Invalid username or password")
    st.stop()

# ---------------------- Begin Main App Code ----------------------
session_id = st.session_state["session_id"]
base_folder = f"bundle_images_{session_id}"

# ----- Automatically clean up previous session files on app start -----
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

clear_old_data()  # Pulizia dei file di sessione al primo avvio

# ---------------------- Helper Functions ----------------------
async def async_download_image(product_code, extension, session):
    if product_code.startswith(('1', '0')):
        product_code = f"D{product_code}"
    url = f"https://cdn.shop-apotheke.com/images/{product_code}-p{extension}.jpg"
    try:
        async with session.get(url) as response:
            if response.status == 200:
                content = await response.read()
                return content, url
            else:
                return None, None
    except Exception:
        return None, None

async def async_get_image_with_fallback(product_code, session):
    # Prova in parallelo le estensioni "1" e "10"
    tasks = [async_download_image(product_code, ext, session) for ext in ["1", "10"]]
    results = await asyncio.gather(*tasks)
    for ext, result in zip(["1", "10"], results):
        content, url = result
        if content:
            return content, ext
    # Se non troviamo l'immagine, prova il fallback se specificato
    fallback_ext = st.session_state.get("fallback_ext", None)
    if fallback_ext:
        content, _ = await async_download_image(product_code, fallback_ext, session)
        if content:
            return content, fallback_ext
    return None, None

def trim(im):
    """Rimuove i bordi bianchi dall'immagine."""
    bg = Image.new(im.mode, im.size, (255, 255, 255))
    diff = ImageChops.difference(im, bg)
    bbox = diff.getbbox()
    if bbox:
        return im.crop(bbox)
    return im

def process_double_bundle_image(image, layout="horizontal"):
    """Processa bundle a due immagini: rimuove i bordi bianchi, unisce due copie e ridimensiona su una tela 1000x1000."""
    image = trim(image)
    width, height = image.size
    if layout.lower() == "automatic":
        chosen_layout = "vertical" if height < width else "horizontal"
    else:
        chosen_layout = layout.lower()
    if chosen_layout == "horizontal":
        merged_width = width * 2
        merged_height = height
        merged_image = Image.new("RGB", (merged_width, merged_height), (255, 255, 255))
        merged_image.paste(image, (0, 0))
        merged_image.paste(image, (width, 0))
    elif chosen_layout == "vertical":
        merged_width = width
        merged_height = height * 2
        merged_image = Image.new("RGB", (merged_width, merged_height), (255, 255, 255))
        merged_image.paste(image, (0, 0))
        merged_image.paste(image, (0, height))
    else:
        merged_width = width * 2
        merged_height = height
        merged_image = Image.new("RGB", (merged_width, merged_height), (255, 255, 255))
        merged_image.paste(image, (0, 0))
        merged_image.paste(image, (width, 0))
    
    scale_factor = min(1000 / merged_width, 1000 / merged_height)
    new_size = (int(merged_width * scale_factor), int(merged_height * scale_factor))
    resized_image = merged_image.resize(new_size, Image.LANCZOS)
    final_image = Image.new("RGB", (1000, 1000), (255, 255, 255))
    x_offset = (1000 - new_size[0]) // 2
    y_offset = (1000 - new_size[1]) // 2
    final_image.paste(resized_image, (x_offset, y_offset))
    return final_image

def process_triple_bundle_image(image, layout="horizontal"):
    """Processa bundle a tre immagini: rimuove i bordi bianchi, unisce tre copie e ridimensiona su una tela 1000x1000."""
    image = trim(image)
    width, height = image.size
    if layout.lower() == "automatic":
        chosen_layout = "vertical" if height < width else "horizontal"
    else:
        chosen_layout = layout.lower()
    if chosen_layout == "horizontal":
        merged_width = width * 3
        merged_height = height
        merged_image = Image.new("RGB", (merged_width, merged_height), (255, 255, 255))
        merged_image.paste(image, (0, 0))
        merged_image.paste(image, (width, 0))
        merged_image.paste(image, (width * 2, 0))
    elif chosen_layout == "vertical":
        merged_width = width
        merged_height = height * 3
        merged_image = Image.new("RGB", (merged_width, merged_height), (255, 255, 255))
        merged_image.paste(image, (0, 0))
        merged_image.paste(image, (0, height))
        merged_image.paste(image, (0, height * 2))
    else:
        merged_width = width * 3
        merged_height = height
        merged_image = Image.new("RGB", (merged_width, merged_height), (255, 255, 255))
        merged_image.paste(image, (0, 0))
        merged_image.paste(image, (width, 0))
        merged_image.paste(image, (width * 2, 0))
    
    scale_factor = min(1000 / merged_width, 1000 / merged_height)
    new_size = (int(merged_width * scale_factor), int(merged_height * scale_factor))
    resized_image = merged_image.resize(new_size, Image.LANCZOS)
    final_image = Image.new("RGB", (1000, 1000), (255, 255, 255))
    x_offset = (1000 - new_size[0]) // 2
    y_offset = (1000 - new_size[1]) // 2
    final_image.paste(resized_image, (x_offset, y_offset))
    return final_image

def save_binary_file(path, data):
    """Salva in maniera sincrona dei dati binari su file."""
    with open(path, 'wb') as f:
        f.write(data)

# ---------------------- Main Processing Function ----------------------
async def process_file_async(uploaded_file, progress_bar=None, layout="horizontal"):
    # Protezione tramite crittografia
    if "encryption_key" not in st.session_state:
        st.session_state["encryption_key"] = Fernet.generate_key()
    key = st.session_state["encryption_key"]
    f = Fernet(key)
    
    file_bytes = uploaded_file.read()
    encrypted_bytes = f.encrypt(file_bytes)
    decrypted_bytes = f.decrypt(encrypted_bytes)
    
    csv_file = BytesIO(decrypted_bytes)
    data = pd.read_csv(csv_file, delimiter=';', dtype=str)
    
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
    error_list = []      # Lista di tuple: (bundle_code, product_code)
    bundle_list = []     # Dettagli: bundle code, lista di product codes, tipo di bundle, flag cross-country
    
    total = len(data)
    
    connector = aiohttp.TCPConnector(limit=100)
    async with aiohttp.ClientSession(connector=connector) as session:
        for i, (_, row) in enumerate(data.iterrows()):
            bundle_code = row['sku'].strip()
            product_codes = [code.strip() for code in row['pzns_in_set'].strip().split(',')]
            num_products = len(product_codes)
            is_uniform = (len(set(product_codes)) == 1)
            bundle_type = f"bundle of {num_products}" if is_uniform else "mixed"
            bundle_cross_country = False
    
            if is_uniform:
                product_code = product_codes[0]
                image_data, used_ext = await async_get_image_with_fallback(product_code, session)
                if used_ext in ["1-fr", "1-de", "1-nl", "1-be"]:
                    bundle_cross_country = True
                folder_name = os.path.join(base_folder, "cross-country") if bundle_cross_country else os.path.join(base_folder, f"bundle_{num_products}")
                os.makedirs(folder_name, exist_ok=True)
                if image_data:
                    try:
                        # Apertura e processing dell'immagine in thread separato
                        img = await asyncio.to_thread(Image.open, BytesIO(image_data))
                        if num_products == 2:
                            final_img = await asyncio.to_thread(process_double_bundle_image, img, layout)
                        elif num_products == 3:
                            final_img = await asyncio.to_thread(process_triple_bundle_image, img, layout)
                        else:
                            final_img = img
                        save_path = os.path.join(folder_name, f"{bundle_code}-h1.jpg")
                        await asyncio.to_thread(final_img.save, save_path, "JPEG", quality=100)
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
                    image_data, used_ext = await async_get_image_with_fallback(product_code, session)
                    if used_ext in ["1-fr", "1-de", "1-nl", "1-be"]:
                        bundle_cross_country = True
                    if image_data:
                        prod_folder = os.path.join(bundle_folder, "cross-country") if used_ext in ["1-fr", "1-de", "1-nl", "1-be"] else bundle_folder
                        os.makedirs(prod_folder, exist_ok=True)
                        file_path = os.path.join(prod_folder, f"{product_code}.jpg")
                        await asyncio.to_thread(save_binary_file, file_path, image_data)
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
    with open(missing_images_csv, "rb") as f_csv:
        missing_images_data = f_csv.read()
    
    bundle_list_df = pd.DataFrame(bundle_list, columns=["sku", "pzns_in_set", "bundle type", "cross-country"])
    bundle_list_csv = "bundle_list.csv"
    bundle_list_df.to_csv(bundle_list_csv, index=False, sep=';')
    with open(bundle_list_csv, "rb") as f_csv:
        bundle_list_data = f_csv.read()
    
    zip_path = f"bundle_images_{session_id}.zip"
    shutil.make_archive("bundle_images_temp", 'zip', base_folder)
    os.rename("bundle_images_temp.zip", zip_path)
    with open(zip_path, "rb") as zip_file:
        zip_bytes = zip_file.read()
    
    return zip_bytes, missing_images_data, missing_images_df, bundle_list_data

# ---------------------- End of Function Definitions ----------------------

# Main UI
st.title("PDM Bundle Image Creator")

st.markdown(
    """
    **How to use:**
    
    1. Create a Quick Report in Akeneo containing the list of products.
    2. Select the following options:
       - File Type: CSV - All Attributes or Grid Context (for Grid Context, select ID and PZN included in the set) - With Codes - Without Media
    3. **Choose the language for language specific photos:** (if needed)
    4. **Choose bundle layout:** (Horizontal, Vertical, or Automatic)
    5. Click **Process CSV** to start the process.
    """
)

if st.button("🧹 Clear Cache and Reset Data"):
    keys_to_keep = {"authenticated", "session_id", "fallback_ext"}
    for key in list(st.session_state.keys()):
        if key not in keys_to_keep:
            del st.session_state[key]
    st.cache_data.clear()
    clear_old_data()
    components.html("<script>window.location.href=window.location.origin+window.location.pathname;</script>", height=0)

st.sidebar.header("What This App Does")
st.sidebar.markdown(
    """
    - ❓ **Automated Bundle Creation:** Automatically create product bundles by downloading and organizing images.
    - 📂 **CSV Upload:** Use a Quick Report in Akeneo.
    - 🔎 **Language Selection:** Choose the language for language specific photos.
    - ✏️ **Dynamic Processing:** Combine images (double/triple) with proper resizing.
    - 🔎 **Layout:** Choose the layout for double/triple bundles.
    - 📁 **Efficient Organization:** Save double/triple bundles in dedicated folders and mixed bundles in separate directories. Language-specific images go to "cross-country".
    - ✏️ **Renames images** using the bundle code.
    - ❌ **Error Logging:** Missing images are logged in a CSV.
    - 📥 **Download:** Get a ZIP with all processed images and reports.
    - 🌐 **Interactive Preview:** Preview and download individual product images from the sidebar.
    """, unsafe_allow_html=True
)

st.sidebar.header("Product Image Preview")
product_code = st.sidebar.text_input("Enter Product Code:")
selected_extension = st.sidebar.selectbox("Select Image Extension:", [str(i) for i in range(1, 19)], key="sidebar_ext")
with st.sidebar:
    col_button, col_spinner = st.columns([2, 1])
    show_image = col_button.button("Show Image")
    spinner_placeholder = col_spinner.empty()

if show_image and product_code:
    with spinner_placeholder:
        with st.spinner("Processing..."):
            preview_url = f"https://cdn.shop-apotheke.com/images/{product_code}-p{selected_extension}.jpg"
            try:
                import requests  # per il download sincrono in anteprima
                response = requests.get(preview_url, stream=True)
                image_data = response.content if response.status_code == 200 else None
            except Exception:
                image_data = None
    if image_data:
        image = Image.open(BytesIO(image_data))
        st.sidebar.image(image, caption=f"Product: {product_code} (p{selected_extension})", use_container_width=True)
        st.sidebar.download_button(
            label="Download Image",
            data=image_data,
            file_name=f"{product_code}-p{selected_extension}.jpg",
            mime="image/jpeg"
        )
    else:
        st.sidebar.error(f"No image found for {product_code} with -p{selected_extension}.jpg")

uploaded_file = st.file_uploader("**Upload CSV File**", type=["csv"], key="file_uploader")
if uploaded_file:
    fallback_language = st.selectbox("**Choose the language for language specific photos:**", options=["None", "FR", "DE", "NL", "BE"], index=0)
    if fallback_language != "None":
        st.session_state["fallback_ext"] = f"1-{fallback_language.lower()}"
    else:
        st.session_state["fallback_ext"] = None

    layout_choice = st.selectbox("**Choose bundle layout:**", options=["Horizontal", "Vertical", "Automatic"], index=2)

    if st.button("Process CSV"):
        start_time = time.time()
        progress_bar = st.progress(0)
        zip_data, missing_images_data, missing_images_df, bundle_list_data = asyncio.run(process_file_async(uploaded_file, progress_bar, layout=layout_choice))
        progress_bar.empty()
        elapsed_time = time.time() - start_time
        minutes = int(elapsed_time // 60)
        seconds = int(elapsed_time % 60)
        st.write(f"Time to download and process images: {minutes} minutes and {seconds} seconds")
        if zip_data:
            st.session_state["zip_data"] = zip_data
            st.session_state["bundle_list_data"] = bundle_list_data
            st.session_state["missing_images_data"] = missing_images_data
            st.session_state["missing_images_df"] = missing_images_df

if "zip_data" in st.session_state:
    st.success("Processing complete! Download your files below.")
    st.download_button(
        label="Download Bundle Image",
        data=st.session_state["zip_data"],
        file_name=f"bundle_images_{session_id}.zip",
        mime="application/zip"
    )
    st.download_button(
        label="Download Bundle List",
        data=st.session_state["bundle_list_data"],
        file_name="bundle_list.csv",
        mime="text/csv"
    )
    if st.session_state["missing_images_df"] is not None and not st.session_state["missing_images_df"].empty:
        st.warning("Some images were not found:")
        st.dataframe(st.session_state["missing_images_df"].reset_index(drop=True))
        st.download_button(
            label="Download Missing Images CSV",
            data=st.session_state["missing_images_data"],
            file_name="missing_images.csv",
            mime="text/csv"
        )
