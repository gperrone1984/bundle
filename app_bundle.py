import streamlit as st
import os
import requests
import pandas as pd
import shutil
from io import BytesIO
from PIL import Image
import time  # Importato per simulare il caricamento nella progress bar

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

# Function to download an image, prioritizing p1 and then p10
def download_image_for_bundle(product_code):
    if product_code.startswith(('1', '0')):
        product_code = f"D{product_code}"
    
    for extension in ["1", "10"]:  # Prioritize p1, then p10
        url = f"https://cdn.shop-apotheke.com/images/{product_code}-p{extension}.jpg"
        response = requests.get(url, stream=True)
        
        if response.status_code == 200:
            return response.content  # Return first successful match
    
    return None  # Return None if no image found

# Function to create directories if they do not exist
def create_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)

# Function to process the uploaded CSV file with a progress bar
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
    create_directory(base_folder)
    
    mixed_sets_needed = False  # Flag to track if we need the mixed_sets folder
    mixed_folder = os.path.join(base_folder, "mixed_sets")
    
    error_list = []
    
    total_rows = len(data)
    progress_bar = st.progress(0)  # Initialize progress bar
    
    for index, row in data.iterrows():
        bundle_code = row['sku'].strip()
        product_codes = row['pzns_in_set'].strip().split(',')
        
        num_products = len(product_codes)
        
        if len(set(product_codes)) == 1:  # Uniform bundle
            folder_name = f"{base_folder}/bundle_{num_products}"
            create_directory(folder_name)
            product_code = product_codes[0]
            image_data = download_image_for_bundle(product_code)  # Try p1, then p10
            
            if image_data:
                with open(os.path.join(folder_name, f"{bundle_code}-h1.jpg"), 'wb') as file:
                    file.write(image_data)
            else:
                error_list.append((bundle_code, product_code))
        else:  # Mixed bundle
            mixed_sets_needed = True  # Mark that at least one mixed bundle exists
            bundle_folder = os.path.join(mixed_folder, bundle_code)
            create_directory(bundle_folder)
            for product_code in product_codes:
                image_data = download_image_for_bundle(product_code)  # Try p1, then p10
                
                if image_data:
                    with open(os.path.join(bundle_folder, f"{product_code}.jpg"), 'wb') as file:
                        file.write(image_data)
                else:
                    error_list.append((bundle_code, product_code))
        
        # Update progress bar
        progress_bar.progress((index + 1) / total_rows)
        time.sleep(0.1)  # Simulazione ritardo per vedere la progressione
        
    # Remove mixed_sets folder if no mixed bundles were found
    if not mixed_sets_needed and os.path.exists(mixed_folder):
        shutil.rmtree(mixed_folder)
    
    # Create missing images report
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

# File uploader
uploaded_file = st.file_uploader("Upload CSV File", type=["csv"])

if uploaded_file:
    with st.spinner("Processing... Please wait..."):  # Show spinner
        zip_data, missing_images_data, missing_images_df = process_file(uploaded_file)
        
    if zip_data:
        st.success("**Processing complete! Download your ZIP file below.**")
        st.download_button(label="📥 Download Images", data=zip_data, file_name="bundle_images.zip", mime="application/zip")
    
    if missing_images_df is not None and not missing_images_df.empty:
        st.warning("**Some images were not found:**")
        st.dataframe(missing_images_df.reset_index(drop=True))
        st.download_button(label="📥 Download Missing Images CSV", data=missing_images_data, file_name="missing_images.csv", mime="text/csv")
