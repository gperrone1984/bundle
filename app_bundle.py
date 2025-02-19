import streamlit as st
import os
import requests
import pandas as pd
import shutil
from io import BytesIO
from PIL import Image, ImageChops

# Streamlit UI
st.title("PDM Bundle Image Creator")

# Instructions
st.markdown("""
📌 **Instructions:**
To prepare the input file, follow these steps:
1. Create a **Quick Report** in Akeneo containing the list of products.
2. Select the following options:
   - File Type: **CSV**
   - **All Attributes** or **Grid Context**, to speed up the download (for **Grid Context** select **ID** and **PZN included in the set**)
   - **With Codes**
   - **Without Media**
""")

# Function to delete the previous bundle_images folder
def clear_old_data():
    if os.path.exists("bundle_images"):
        shutil.rmtree("bundle_images")
    if os.path.exists("bundle_images.zip"):
        os.remove("bundle_images.zip")
    if os.path.exists("missing_images.csv"):
        os.remove("missing_images.csv")
    if os.path.exists("bundle_list.csv"):
        os.remove("bundle_list.csv")

# Button to clear cache and delete old files
if st.button("🧹 Clear Cache and Reset Data"):
    st.session_state.clear()
    st.cache_data.clear()
    clear_old_data()  # Delete old files
    st.rerun()

# Sidebar with app functionalities
st.sidebar.header("🔹 What This App Does")
st.sidebar.markdown("""
- ❓ This app automates the **creation of product bundles** by **downloading and organizing product images**
- 📂 **Uploads a CSV file** containing bundle and product information.
- 🌐 **Downloads images** for each product from a specified URL.
- 🔎 **Searches** first for the manufacturer image (p1), then the Fotobox image (p10).
- 🗂 **Organizes images** into folders based on the type of bundle.
- ✏️ **Renames images** for bundles double, triple etc. using the bundle code.
- 📁 **Sorts mixed-set images** into separate folders named after the bundle code.
- ❌ **Identifies missing images** and show/logs them in a separate file.
- 📥 **Generates a ZIP file** containing all retrieved images.
- 📥 Generates a CSV file with a **list of Bundle** in the file.
- 🔎 **Tool Preview and download product images:** Useful when p1 or p10 images are missing or when the p1 image is of poor quality.
""")

# Function to download an image for preview
def download_image(product_code, extension):
    if product_code.startswith(('1', '0')):
        product_code = f"D{product_code}"
    
    url = f"https://cdn.shop-apotheke.com/images/{product_code}-p{extension}.jpg"
    response = requests.get(url, stream=True)
    
    if response.status_code == 200:
        return response.content, url
    return None, None

# Function to trim white borders from an image
def trim(im):
    bg = Image.new(im.mode, im.size, (255, 255, 255))  # White background
    diff = ImageChops.difference(im, bg)
    bbox = diff.getbbox()
    if bbox:
        return im.crop(bbox)
    return im

# Function to create a duplicated image for double bundles
def create_double_image(image_data):
    image = Image.open(BytesIO(image_data))
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

# Function to process the uploaded CSV file
def process_file(uploaded_file):
    uploaded_file.seek(0)
    data = pd.read_csv(uploaded_file, delimiter=';', dtype=str)
    
    required_columns = {'sku', 'pzns_in_set'}
    missing_columns = required_columns - set(data.columns)
    if missing_columns:
        st.error(f"Missing required columns: {', '.join(missing_columns)}")
        return None, None, None
    
    data = data[list(required_columns)]
    data.dropna(inplace=True)
    
    base_folder = "bundle_images"
    os.makedirs(base_folder, exist_ok=True)
    
    for _, row in data.iterrows():
        bundle_code = row['sku'].strip()
        product_codes = row['pzns_in_set'].strip().split(',')
        num_products = len(product_codes)
        
        if num_products == 2 and len(set(product_codes)) == 1:
            folder_name = f"{base_folder}/bundle_{num_products}"
            os.makedirs(folder_name, exist_ok=True)
            image_data = download_image(product_codes[0], "1")[0] or download_image(product_codes[0], "10")[0]
            
            if image_data:
                final_image = create_double_image(image_data)
                final_image.save(os.path.join(folder_name, f"{bundle_code}-h1.jpg"), "JPEG", quality=95)
    
    st.success("Processing complete!")

uploaded_file = st.file_uploader("Upload CSV File", type=["csv"])

if uploaded_file:
    with st.spinner("Processing..."):
        process_file(uploaded_file)
