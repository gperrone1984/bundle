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
    If these are not found and if the user has selected a fallback (FR or DE),
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
    else:  # vertical
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
    else:  # vertical
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

# ---------------------- Main Processing Function ----------------------
def process_file(uploaded_file, progress_bar=None, orientation="horizontal"):
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
        bundle_type = f"bundle of {num_products}" if is_uniform else "mixed"
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
                        final_img = process_double_bundle_image(img, orientation=orientation)
                    elif num_products == 3:
                        final_img = process_triple_bundle_image(img, orientation=orientation)
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
    
    zip_path = f"bundle_images_{session_id}.zip"
    shutil.make_archive("bundle_images_temp", 'zip', base_folder)
    os.rename("bundle_images_temp.zip", zip_path)
    with open(zip_path, "rb") as zip_file:
        return zip_file.read(), missing_images_data, missing_images_df, bundle_list_data

# ---------------------- End of Function Definitions ----------------------

# Main UI
st.title("PDM Bundle Image Creator")

st.markdown("""
📌 **Instructions:**
1. Create a **Quick Report** in Akeneo containing the list of products.
2. Select the following options:
   - File Type: **CSV**
   - **All Attributes** or **Grid Context** (for Grid Context select **ID** and **PZN included in the set**)
   - **With Codes**
   - **Without Media**
""")

# Clear Cache and Reset Data button
if st.button("🧹 Clear Cache and Reset Data"):
    st.session_state.clear()
    st.cache_data.clear()
    clear_old_data()
    components.html("<script>window.location.href=window.location.origin+window.location.pathname;</script>", height=0)

# Sidebar: What This App Does (Semplified with icons)
st.sidebar.header("🔹 What This App Does")
st.sidebar.markdown("""
- 🤖 **Automated Bundle Creation:** Automatically create product bundles by downloading and organizing images.
- 📄 **CSV Upload:** Import a CSV report with product info.
- 🔍 **Smart Image Retrieval:** Fetch high-quality images (p1, then p10).
- 🌐 **Language Selection:** You can select the language for cross-country images.
- 🎨 **Dynamic Processing:** Combine images (double/triple) with proper resizing.
- ↔️ **Orientation Choice:** Scegli se affiancare le immagini orizzontalmente o verticalmente.
- 📁 **Efficient Organization:** Save uniform bundles in dedicated folders and mixed bundles in separate directories. Language specific images go to "cross-country".
- 🚨 **Error Logging:** Missing images are logged in a CSV.
- 📦 **Download:** Get a ZIP with all processed images and reports.
- 👀 **Interactive Preview:** Preview and download individual product images from the sidebar.
""", unsafe_allow_html=True)

# Sidebar: Orientation and Product Image Preview
st.sidebar.header("🔎 Product Image Preview & Orientation")
orientation = st.sidebar.selectbox("Seleziona Orientamento:", ["horizontal", "vertical"])
product_code = st.sidebar.text_input("Enter Product Code:")
selected_extension = st.sidebar.selectbox("Select Image Extension:", [str(i) for i in range(1, 19)], key="sidebar_ext")
with st.sidebar:
    col_button, col_spinner = st.columns([2, 1])
    show_image = col_button.button("Show Image")
    spinner_placeholder = col_spinner.empty()

if show_image and product_code:
    with spinner_placeholder:
        with st.spinner("Processing..."):
            image_data, image_url = download_image(product_code, selected_extension)
    if image_data:
        image = Image.open(BytesIO(image_data))
        # Esempio: se vuoi visualizzare un bundle doppio in anteprima con l'orientamento scelto
        preview_img = process_double_bundle_image(image, orientation=orientation)
        st.sidebar.image(preview_img, caption=f"Anteprima ({orientation}) - {product_code}", use_column_width=True)
        st.sidebar.download_button(
            label="📥 Download Image",
            data=image_data,
            file_name=f"{product_code}-p{selected_extension}.jpg",
            mime="image/jpeg"
        )
    else:
        st.sidebar.error(f"⚠️ No image found for {product_code} with -p{selected_extension}.jpg")

# Main Content: File Uploader and Process CSV with FR/DE buttons and cross-country label
uploaded_file = st.file_uploader("Upload CSV File", type=["csv"], key="file_uploader")
if uploaded_file:
    cols = st.columns([2, 1, 1, 1])
    with cols[0]:
        if st.button("Process CSV"):
            start_time = time.time()  # Start timer
            progress_bar = st.progress(0)
            zip_data, missing_images_data, missing_images_df, bundle_list_data = process_file(uploaded_file, progress_bar, orientation=orientation)
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
    with cols[1]:
        st.markdown("**Cross-country photos:**")
    with cols[2]:
        if st.button("FR", key="fr_button_main"):
            st.session_state["fallback_ext"] = "1-fr"
    with cols[3]:
        if st.button("DE", key="de_button_main"):
            st.session_state["fallback_ext"] = "1-de"

if "zip_data" in st.session_state:
    st.success("**Processing complete! Download your files below.**")
    st.download_button(
        label="🖼️ Download Bundle Image",
        data=st.session_state["zip_data"],
        file_name=f"bundle_images_{session_id}.zip",
        mime="application/zip"
    )
    st.download_button(
        label="📋 Download Bundle List",
        data=st.session_state["bundle_list_data"],
        file_name="bundle_list.csv",
        mime="text/csv"
    )
    if st.session_state["missing_images_df"] is not None and not st.session_state["missing_images_df"].empty:
        st.warning("**Some images were not found:**")
        st.dataframe(st.session_state["missing_images_df"].reset_index(drop=True))
        st.download_button(
            label="⚠️ Download Missing Images CSV",
            data=st.session_state["missing_images_data"],
            file_name="missing_images.csv",
            mime="text/csv"
        )
