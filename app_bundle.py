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
- 📁 **Sorts mixed-set images** into separate folders named after the bundle code (only if needed).
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
    if os.path.exists("bundle_list.csv"):
        os.remove("bundle_list.csv")
    st.rerun()

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

# Function to process the uploaded CSV file
def process_file(uploaded_file):
    uploaded_file.seek(0)  # Reset file pointer to ensure fresh read
    data = pd.read_csv(uploaded_file, delimiter=';', dtype=str)
    
    # Ensure necessary columns exist
    required_columns = {'sku', 'pzns_in_set'}
    missing_columns = required_columns - set(data.columns)
    if missing_columns:
        st.error(f"Missing required columns: {', '.join(missing_columns)}")
        return None, None, None, None
    
    data = data[list(required_columns)]  # Keep only required columns
    data.dropna(inplace=True)
    
    base_folder = "bundle_images"
    create_directory(base_folder)
    
    mixed_sets_needed = False  # Flag to track if we need the mixed_sets folder
    mixed_folder = os.path.join(base_folder, "mixed_sets")
    
    error_list = []
    bundle_list = []  # New list to store bundle details

    for _, row in data.iterrows():
        bundle_code = row['sku'].strip()
        product_codes = row['pzns_in_set'].strip().split(',')
        
        num_products = len(product_codes)
        bundle_type = f"bundle of {num_products}"
        
        bundle_list.append([bundle_code, ', '.join(product_codes), bundle_type])  # Add to bundle list

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

    # Remove mixed_sets folder if no mixed bundles were found
    if not mixed_sets_needed and os.path.exists(mixed_folder):
        shutil.rmtree(mixed_folder)

    # Create missing images report
    missing_images_df = pd.DataFrame(error_list, columns=["PZN Bundle", "PZN with image missing"])
    missing_images_csv = "missing_images.csv"
    missing_images_df.to_csv(missing_images_csv, index=False, sep=';')

    with open(missing_images_csv, "rb") as f:
        missing_images_data = f.read()

    # Create bundle list CSV
    bundle_list_df = pd.DataFrame(bundle_list, columns=["sku", "pzns_in_set", "bundle type"])
    bundle_list_csv = "bundle_list.csv"
    bundle_list_df.to_csv(bundle_list_csv, index=False, sep=';')

    with open(bundle_list_csv, "rb") as f:
        bundle_list_data = f.read()

    # Create ZIP file of images
    zip_path = "bundle_images.zip"
    shutil.make_archive("bundle_images_temp", 'zip', base_folder)
    os.rename("bundle_images_temp.zip", zip_path)

    with open(zip_path, "rb") as zip_file:
        return zip_file.read(), missing_images_data, missing_images_df, bundle_list_data

uploaded_file = st.file_uploader("Upload CSV File", type=["csv"])

if uploaded_file:
    with st.spinner("Processing..."):
        zip_data, missing_images_data, missing_images_df, bundle_list_data = process_file(uploaded_file)

    if zip_data:
        st.success("**Processing complete! Download your files below.**")
        
        # Download buttons
        st.download_button(label="📥 Download Images", data=zip_data, file_name="bundle_images.zip", mime="application/zip")
        st.download_button(label="📥 Download Bundle List", data=bundle_list_data, file_name="bundle_list.csv", mime="text/csv")
        
        if missing_images_df is not None and not missing_images_df.empty:
            st.warning("**Some images were not found:**")
            st.dataframe(missing_images_df.reset_index(drop=True))
            st.download_button(label="📥 Download Missing Images CSV", data=missing_images_data, file_name="missing_images.csv", mime="text/csv")
