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

# Product Image Preview Section
st.sidebar.header("🔎 Product Image Preview")
product_code = st.sidebar.text_input("Enter Product Code:")
selected_extension = st.sidebar.selectbox("Select Image Extension:", [str(i) for i in range(1, 19)])

def download_image(product_code, extension):
    if product_code.startswith(('1', '0')):
        product_code = f"D{product_code}"
    
    url = f"https://cdn.shop-apotheke.com/images/{product_code}-p{extension}.jpg"
    response = requests.get(url, stream=True)
    
    if response.status_code == 200:
        return response.content, url
    return None, None

if st.sidebar.button("Show Image") and product_code:
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

# Function to trim white borders
def trim(im):
    bg = Image.new(im.mode, im.size, (255, 255, 255))
    diff = ImageChops.difference(im, bg)
    bbox = diff.getbbox()
    if bbox:
        return im.crop(bbox)
    return im

# Function to process the uploaded CSV file
def process_file(uploaded_file):
    uploaded_file.seek(0)
    data = pd.read_csv(uploaded_file, delimiter=';', dtype=str)
    
    required_columns = {'sku', 'pzns_in_set'}
    missing_columns = required_columns - set(data.columns)
    if missing_columns:
        st.error(f"Missing required columns: {', '.join(missing_columns)}")
        return None, None
    
    data = data[list(required_columns)]
    data.dropna(inplace=True)
    
    base_folder = "bundle_images"
    os.makedirs(base_folder, exist_ok=True)
    mixed_folder = os.path.join(base_folder, "mixed_sets")
    os.makedirs(mixed_folder, exist_ok=True)
    
    error_list = []
    for _, row in data.iterrows():
        bundle_code = row['sku'].strip()
        product_codes = row['pzns_in_set'].strip().split(',')
        
        folder_name = os.path.join(base_folder, bundle_code)
        os.makedirs(folder_name, exist_ok=True)
        
        for product_code in product_codes:
            image_data = download_image(product_code, "1")[0] or download_image(product_code, "10")[0]
            
            if image_data:
                with open(os.path.join(folder_name, f"{product_code}.jpg"), 'wb') as file:
                    file.write(image_data)
            else:
                error_list.append((bundle_code, product_code))
    
    zip_path = "bundle_images.zip"
    shutil.make_archive("bundle_images_temp", 'zip', base_folder)
    os.rename("bundle_images_temp.zip", zip_path)
    
    with open(zip_path, "rb") as zip_file:
        return zip_file.read()

uploaded_file = st.file_uploader("Upload CSV File", type=["csv"])

if uploaded_file:
    with st.spinner("Processing..."):
        zip_data = process_file(uploaded_file)
    if zip_data:
        st.success("Processing complete! Download your files below.")
        st.download_button(label="📥 Download Bundle Images", data=zip_data, file_name="bundle_images.zip", mime="application/zip")
