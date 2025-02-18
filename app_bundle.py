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
- 📜 **Creates a complete bundle list** including SKU, products in the set, and bundle type.
""")

# Function to create directories if they do not exist
def create_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)

# Function to process the uploaded CSV file and create the bundle list
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
    bundle_list = []  # List for the bundle CSV
    
    for _, row in data.iterrows():
        bundle_code = row['sku'].strip()
        product_codes = row['pzns_in_set'].strip().split(',')
        
        num_products = len(product_codes)
        if len(set(product_codes)) == 1:
            bundle_type = f"Bundle of {num_products}"  # Ex: "Bundle of 2", "Bundle of 3"
        else:
            bundle_type = "Mixed"

        # Add to bundle list
        bundle_list.append((bundle_code, ",".join(product_codes), bundle_type))

    # Remove mixed_sets folder if no mixed bundles were found
    if not mixed_sets_needed and os.path.exists(mixed_folder):
        shutil.rmtree(mixed_folder)
    
    # Create bundle list CSV
    bundle_df = pd.DataFrame(bundle_list, columns=["sku", "pzns_in_set", "bundle type"])
    bundle_csv = "all_bundles.csv"
    bundle_df.to_csv(bundle_csv, index=False, sep=';')

    with open(bundle_csv, "rb") as f:
        bundle_data = f.read()

    return bundle_data

# File uploader
uploaded_file = st.file_uploader("Upload CSV File", type=["csv"])

if uploaded_file:
    with st.spinner("Processing..."):
        bundle_data = process_file(uploaded_file)
    
    if bundle_data:
        st.success("**Processing complete! Download your files below.**")
        st.info("📜 **Download the complete bundle list**")
        st.download_button(label="📥 Download Bundle List", data=bundle_data, file_name="all_bundles.csv", mime="text/csv")
