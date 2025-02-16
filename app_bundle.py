import streamlit as st
import os
import requests
import pandas as pd
import shutil
from io import BytesIO

# Streamlit UI
st.title("PDM Bundle Image Creator")

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

# Sidebar for image preview and download
st.sidebar.header("🔍 Product Image Preview")
product_code = st.sidebar.text_input("Enter Product Code:")
image_type = st.sidebar.selectbox("Select Image Type:", ["p1", "p10", "Custom"], index=0)
custom_suffix = st.sidebar.text_input("Custom Suffix (if selected)", "")

if st.sidebar.button("Preview Image") and product_code:
    suffix = custom_suffix if image_type == "Custom" else image_type
    image_url = f"https://cdn.shop-apotheke.com/images/{product_code}-{suffix}.jpg"
    response = requests.get(image_url, stream=True)
    if response.status_code == 200:
        st.sidebar.image(image_url, caption=f"Preview: {product_code}-{suffix}.jpg")
        st.sidebar.download_button("📥 Download Image", response.content, file_name=f"{product_code}-{suffix}.jpg", mime="image/jpeg")
    else:
        st.sidebar.error("Image not found. Please check the product code and suffix.")

# Instructions for the input file structure
st.markdown("""
### 📌 Instructions:
To prepare the input file, follow these steps:
1. Create a **Quick Report** in Akeneo containing the list of products.
2. Select the following options:
   - File Type: **CSV**
   - **All Attributes** or **Grid Context**, to speed up the download (for **Grid Context** select **ID** and **PZN included in the set**)
   - **With Codes**
   - **Without Media**
""")

st.write("Upload a CSV file with bundle codes to download and rename corresponding images.")

# Function to download an image from a predefined URL
def download_image(product_code):
    if product_code.startswith(('1', '0')):
        product_code = f"D{product_code}"
    
    base_url = "https://cdn.shop-apotheke.com/images/{}-p{}.jpg"
    for suffix in [1, 10]:  # Try suffix p1 first, then p10
        url = base_url.format(product_code, suffix)
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            return response.content  # Returns image content if found
    return None  # Returns None if the image is not found

# Function to create directories if they do not exist
def create_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)

# File uploader widget
uploaded_file = st.file_uploader("Upload CSV File", type=["csv"])

# Process the uploaded file if available
if uploaded_file:
    with st.spinner("Processing..."):
        zip_data, missing_images_data, missing_images_df = process_file(uploaded_file)
    st.success("**Processing complete! Download your ZIP file below.**")
    
    # Download button for the ZIP file
    st.download_button(label="📥 Download Images", data=zip_data, file_name="bundle_images.zip", mime="application/zip")
    
    # Display missing images if any
    if not missing_images_df.empty:
        st.warning("**Some images were not found:**")
        st.dataframe(missing_images_df.reset_index(drop=True))  # Display missing images list
        
        # Download button for missing images CSV
        st.download_button(label="📥 Download Missing Images CSV", data=missing_images_data, file_name="missing_images.csv", mime="text/csv")
