import streamlit as st
import os
import requests
import pandas as pd
import shutil
from io import BytesIO

def download_image(product_code):
    if product_code.startswith(('1', '0')):
        product_code = f"D{product_code}"
    
    base_url = "https://cdn.shop-apotheke.com/images/{}-p{}.jpg"
    for suffix in [1, 10]:
        url = base_url.format(product_code, suffix)
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            return response.content  # Restituisce il contenuto dell'immagine
    return None

def create_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)

def process_file(uploaded_file):
    data = pd.read_csv(uploaded_file, delimiter=';', dtype=str)
    data.dropna(inplace=True)
    
    base_folder = "bundle_images"
    mixed_folder = os.path.join(base_folder, "mixed_sets")
    create_directory(base_folder)
    create_directory(mixed_folder)
    
    error_list = []
    
    for _, row in data.iterrows():
        bundle_code = row['sku'].strip()
        product_codes = row['pzns_in_set'].strip().split(',')
        
        num_products = len(product_codes)
        
        if len(set(product_codes)) == 1:
            folder_name = f"{base_folder}/bundle_{num_products}"
            create_directory(folder_name)
            product_code = product_codes[0]
            image_data = download_image(product_code)
            if image_data:
                with open(os.path.join(folder_name, f"{bundle_code}-h1.jpg"), 'wb') as file:
                    file.write(image_data)
            else:
                error_list.append(f"{bundle_code},{product_code}")
        else:
            bundle_folder = os.path.join(mixed_folder, bundle_code)
            create_directory(bundle_folder)
            for product_code in product_codes:
                image_data = download_image(product_code)
                if image_data:
                    with open(os.path.join(bundle_folder, f"{product_code}.jpg"), 'wb') as file:
                        file.write(image_data)
                else:
                    error_list.append(f"{bundle_code},{product_code}")
    
    if error_list:
        with open(os.path.join(base_folder, "missing_images.txt"), 'w') as file:
            file.write("\n".join(error_list))
    
    shutil.make_archive(base_folder, 'zip', base_folder)
    
    with open("bundle_images.zip", "rb") as zip_file:
        return zip_file.read()

# Streamlit UI
st.title("PDM Bundle Image Creation")
st.write("Upload a CSV file with bundle codes and download the corresponding images.")

uploaded_file = st.file_uploader("Upload CSV file", type=["csv"])

if uploaded_file:
    with st.spinner("Processing..."):
        zip_data = process_file(uploaded_file)
    st.success("Processing completed! Download the ZIP file below.")
    st.download_button(label="📥 Download the images", data=zip_data, file_name="bundle_images.zip", mime="application/zip")
