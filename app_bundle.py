import streamlit as st
import os
import requests
import pandas as pd
import shutil
from io import BytesIO
from PIL import Image

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
- 📂 **Uploads a CSV file** containing bundle and product information.
- 🌐 **Fetches images** for each product from a predefined URL.
- 🔎 **Searches first for the manufacturer image (p1), then the Fotobox image (p10).**
- 🗂 **Organizes images** into folders based on the type of bundle.
- ✏️ **Renames images** for uniform bundles using the bundle code.
- 📁 **Sorts mixed-set images** into separate folders named after the bundle code.
- ❌ **Identifies missing images** and logs them in a separate file.
- 📥 **Generates a ZIP file** containing all retrieved images.
""")

# Button to clear cache and delete old files
if st.button("🔄 Clear Cache and Files"):
    st.cache_data.clear()
    if os.path.exists("bundle_images"):
        shutil.rmtree("bundle_images")
    if os.path.exists("bundle_images.zip"):
        os.remove("bundle_images.zip")
    if os.path.exists("missing_images.csv"):
        os.remove("missing_images.csv")
    st.rerun()

# Function to download an image from a predefined URL
def download_image(product_code):
    if product_code.startswith(('1', '0')):
        product_code = f"D{product_code}"
    
    for extension in ["1", "10"]:
        url = f"https://cdn.shop-apotheke.com/images/{product_code}-p{extension}.jpg"
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            return response.content, url
    return None, None

# Product Image Preview Section
st.sidebar.header("🔎 Product Image Preview")
product_code = st.sidebar.text_input("Enter Product Code:")
selected_extension = st.sidebar.selectbox("Select Image Extension:", [str(i) for i in range(1, 19)])

# Display image preview
if st.sidebar.button("Show Image") and product_code:
    image_data, image_url = download_image(product_code)
    
    if image_data:
        image = Image.open(BytesIO(image_data))
        st.sidebar.image(image, caption=f"Product: {product_code}", use_container_width=True)
        
        # Download button for the image
        st.sidebar.download_button(
            label="📥 Download Image",
            data=image_data,
            file_name=f"{product_code}.jpg",
            mime="image/jpeg"
        )
    else:
        st.sidebar.error(f"Image not found for {product_code}.")

# Function to create directories if they do not exist
def create_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)

# Function to process the uploaded CSV file
def process_file(uploaded_file):
    uploaded_file.seek(0)  # Reset file pointer to ensure fresh read
    data = pd.read_csv(uploaded_file, delimiter=';', dtype=str)
    
    # Ensure necessary columns exist
    required_columns = {'sku', 'pzns_in_set'}
    missing_columns = required_columns - set(data.columns)
    if missing_columns:
        st.error(f"Missing required columns: {', '.join(missing_columns)}")
        return None, None, None
    
    data = data[list(required_columns)]  # Keep only required columns
    data.dropna(inplace=True)
    
    base_folder = "bundle_images"
    create_directory(base_folder)  # Crea la cartella principale solo una volta
    mixed_bundles = []  # Lista per verificare se ci sono bundle misti
    
    error_list = []
    
    for _, row in data.iterrows():
        bundle_code = row['sku'].strip()
        product_codes = row['pzns_in_set'].strip().split(',')
        
        num_products = len(product_codes)
        
        if len(set(product_codes)) == 1:
            folder_name = f"{base_folder}/bundle_{num_products}"
            create_directory(folder_name)
            product_code = product_codes[0]
            image_data, _ = download_image(product_code)
            if image_data:
                with open(os.path.join(folder_name, f"{bundle_code}-h1.jpg"), 'wb') as file:
                    file.write(image_data)
            else:
                error_list.append((bundle_code, product_code))
        else:
            mixed_bundles.append(bundle_code)  # Aggiunge il bundle misto alla lista
            bundle_folder = os.path.join(base_folder, "mixed_sets", bundle_code)
            create_directory(bundle_folder)
            for product_code in product_codes:
                image_data, _ = download_image(product_code)
                if image_data:
                    with open(os.path.join(bundle_folder, f"{product_code}.jpg"), 'wb') as file:
                        file.write(image_data)
                else:
                    error_list.append((bundle_code, product_code))

    # Creazione della cartella 'mixed_sets' solo se esistono bundle misti
    if not mixed_bundles:
        shutil.rmtree(os.path.join(base_folder, "mixed_sets"), ignore_errors=True)

    missing_images_df = pd.DataFrame(error_list, columns=["PZN Bundle", "PZN with image missing"])
    missing_images_csv = "missing_images.csv"
    
    missing_images_df.to_csv(missing_images_csv, index=False, sep=';')
    
    with open(missing_images_csv, "rb") as f:
        missing_images_data = f.read()
    
    zip_path = "bundle_images.zip"
    shutil.make_archive("bundle_images_temp", 'zip', base_folder)
    os.rename("bundle_images_temp.zip", zip_path)
    
    with open(zip_path, "rb") as zip_file:
        return zip_file.read(), missing_images_data, missing_images_df
