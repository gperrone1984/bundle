import streamlit as st
import streamlit.components.v1 as components
import os
import requests
import pandas as pd
import shutil
from io import BytesIO
from PIL import Image, ImageChops

# ----- Pulizia automatica dello stato all'avvio dell'app -----
st.session_state.clear()

# ---------------------- Function Definitions ----------------------

def download_image(product_code, extension):
    if product_code.startswith(('1', '0')):
        product_code = f"D{product_code}"
    url = f"https://cdn.shop-apotheke.com/images/{product_code}-p{extension}.jpg"
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        return response.content, url
    return None, None

def trim(im):
    bg = Image.new(im.mode, im.size, (255, 255, 255))
    diff = ImageChops.difference(im, bg)
    bbox = diff.getbbox()
    if bbox:
        return im.crop(bbox)
    return im

def process_double_bundle_image(image):
    image = trim(image)
    width, height = image.size
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

def process_triple_bundle_image(image):
    image = trim(image)
    width, height = image.size
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

def clear_old_data():
    if os.path.exists("bundle_images"):
        shutil.rmtree("bundle_images")
    if os.path.exists("bundle_images.zip"):
        os.remove("bundle_images.zip")
    if os.path.exists("missing_images.csv"):
        os.remove("missing_images.csv")
    if os.path.exists("bundle_list.csv"):
        os.remove("bundle_list.csv")

def process_file(uploaded_file, progress_bar=None):
    uploaded_file.seek(0)
    data = pd.read_csv(uploaded_file, delimiter=';', dtype=str)
    
    required_columns = {'sku', 'pzns_in_set'}
    missing_columns = required_columns - set(data.columns)
    if missing_columns:
        st.error(f"Missing required columns: {', '.join(missing_columns)}")
        return None, None, None, None
    
    data = data[list(required_columns)]
    data.dropna(inplace=True)
    
    base_folder = "bundle_images"
    os.makedirs(base_folder, exist_ok=True)
    
    mixed_sets_needed = False
    mixed_folder = os.path.join(base_folder, "mixed_sets")
    error_list = []      # Lista di tuple (bundle_code, product_code) per cui manca l'immagine
    bundle_list = []     # Lista per memorizzare i dettagli del bundle
    
    total = len(data)
    for i, (_, row) in enumerate(data.iterrows()):
        bundle_code = row['sku'].strip()
        product_codes = [code.strip() for code in row['pzns_in_set'].strip().split(',')]
        num_products = len(product_codes)
        
        if len(set(product_codes)) == 1:
            bundle_type = f"bundle of {num_products}"
        else:
            bundle_type = "mixed"
        bundle_list.append([bundle_code, ', '.join(product_codes), bundle_type])
        
        if len(set(product_codes)) == 1:  # Bundle uniforme
            folder_name = f"{base_folder}/bundle_{num_products}"
            os.makedirs(folder_name, exist_ok=True)
            product_code = product_codes[0]
            image_data = download_image(product_code, "1")[0] or download_image(product_code, "10")[0]
            if image_data:
                try:
                    img = Image.open(BytesIO(image_data))
                    if num_products == 2:
                        final_img = process_double_bundle_image(img)
                    elif num_products == 3:
                        final_img = process_triple_bundle_image(img)
                    else:
                        final_img = img
                    final_img.save(os.path.join(folder_name, f"{bundle_code}-h1.jpg"), "JPEG", quality=95)
                except Exception as e:
                    st.error(f"Error processing image for bundle {bundle_code}: {e}")
                    error_list.append((bundle_code, product_code))
            else:
                error_list.append((bundle_code, product_code))
        else:  # Bundle misto
            mixed_sets_needed = True
            bundle_folder = os.path.join(mixed_folder, bundle_code)
            os.makedirs(bundle_folder, exist_ok=True)
            for product_code in product_codes:
                image_data = download_image(product_code, "1")[0] or download_image(product_code, "10")[0]
                if image_data:
                    with open(os.path.join(bundle_folder, f"{product_code}.jpg"), 'wb') as file:
                        file.write(image_data)
                else:
                    error_list.append((bundle_code, product_code))
        
        if progress_bar is not None:
            progress_bar.progress((i + 1) / total)
    
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
    
    bundle_list_df = pd.DataFrame(bundle_list, columns=["sku", "pzns_in_set", "bundle type"])
    bundle_list_csv = "bundle_list.csv"
    bundle_list_df.to_csv(bundle_list_csv, index=False, sep=';')
    with open(bundle_list_csv, "rb") as f:
        bundle_list_data = f.read()
    
    zip_path = "bundle_images.zip"
    shutil.make_archive("bundle_images_temp", 'zip', base_folder)
    os.rename("bundle_images_temp.zip", zip_path)
    with open(zip_path, "rb") as zip_file:
        return zip_file.read(), missing_images_data, missing_images_df, bundle_list_data

# ---------------------- End of Function Definitions ----------------------

# Main UI
st.title("PDM Bundle Image Creator")

st.markdown("""
📌 **Instructions:**
To prepare the input file, follow these steps:
1. Create a **Quick Report** in Akeneo containing the list of products.
2. Select the following options:
   - File Type: **CSV**
   - **All Attributes** or **Grid Context** (for **Grid Context** select **ID** and **PZN included in the set**)
   - **With Codes**
   - **Without Media**
""")

# Clear Cache Button: elimina lo stato, i file e ricarica la pagina iniziale
if st.button("🧹 Clear Cache and Reset Data"):
    st.session_state.clear()
    st.cache_data.clear()
    clear_old_data()
    components.html("<script>window.location.href=window.location.origin+window.location.pathname;</script>", height=0)

# Sidebar: Funzionalità dell'app
st.sidebar.header("🔹 What This App Does")
st.sidebar.markdown("""
- Automates the creation of product bundles by downloading and organizing product images.
- Upload a CSV file with bundle and product information.
- Downloads images for each product from a specified URL.
- Searches first for the manufacturer image (p1), then the Fotobox image (p10).
- Organizes images into folders based on the bundle type.
- Renames images for bundles double, triple etc. using the bundle code.
- Sorts mixed-set images into separate folders.
- Identifies missing images and logs them in a separate file.
- Generates a ZIP file of retrieved images and a CSV file with bundle details.
- Provides a tool to preview and download product images.
""")

# Product Image Preview Section (Sidebar)
st.sidebar.header("🔎 Product Image Preview")
product_code = st.sidebar.text_input("Enter Product Code:")
selected_extension = st.sidebar.selectbox("Select Image Extension:", [str(i) for i in range(1, 19)])
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
        st.sidebar.image(image, caption=f"Product: {product_code} (p{selected_extension})", use_container_width=True)
        st.sidebar.download_button(
            label="📥 Download Image",
            data=image_data,
            file_name=f"{product_code}-p{selected_extension}.jpg",
            mime="image/jpeg"
        )
    else:
        st.sidebar.error(f"⚠️ No image found for {product_code} with -p{selected_extension}.jpg")

# Main Content: File Upload & Processing (con progress bar)
uploaded_file = st.file_uploader("Upload CSV File", type=["csv"], key="file_uploader")
if uploaded_file:
    progress_bar = st.progress(0)
    zip_data, missing_images_data, missing_images_df, bundle_list_data = process_file(uploaded_file, progress_bar)
    progress_bar.empty()
    if zip_data:
        st.success("**Processing complete! Download your files below.**")
        st.download_button(label="📥 **Download Images for Bundle Creation**", data=zip_data, file_name="bundle_images.zip", mime="application/zip")
        st.download_button(label="📥 Download Bundle List", data=bundle_list_data, file_name="bundle_list.csv", mime="text/csv")
        if missing_images_df is not None and not missing_images_df.empty:
            st.warning("**Some images were not found:**")
            st.dataframe(missing_images_df.reset_index(drop=True))
            st.download_button(label="📥 Download Missing Images CSV", data=missing_images_data, file_name="missing_images.csv", mime="text/csv")
