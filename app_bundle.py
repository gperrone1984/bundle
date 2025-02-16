import streamlit as st
import os
import requests
import pandas as pd
import shutil
from io import BytesIO

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

# Function to process the uploaded CSV file
def process_file(uploaded_file):
    data = pd.read_csv(uploaded_file, delimiter=';', dtype=str)  # Read CSV file
    data.dropna(inplace=True)  # Remove rows with missing values
    
    base_folder = "bundle_images"  # Main folder for storing images
    mixed_folder = os.path.join(base_folder, "mixed_sets")  # Folder for mixed bundles
    create_directory(base_folder)
    create_directory(mixed_folder)
    
    error_list = []  # List to store missing images
    
    # Iterate through each row in the CSV file
    for _, row in data.iterrows():
        bundle_code = row['sku'].strip()  # Get bundle code
        product_codes = row['pzns_in_set'].strip().split(',')  # Get product codes in the bundle
        
        num_products = len(product_codes)  # Count the number of products in the bundle
        
        if len(set(product_codes)) == 1:  # If all product codes are the same, it's a uniform bundle
            folder_name = f"{base_folder}/bundle_{num_products}"  # Folder name based on product count
            create_directory(folder_name)
            product_code = product_codes[0]
            image_data = download_image(product_code)
            if image_data:
                with open(os.path.join(folder_name, f"{bundle_code}-h1.jpg"), 'wb') as file:
                    file.write(image_data)  # Save the downloaded image
            else:
                error_list.append((bundle_code, product_code))  # Log missing images
        else:
            bundle_folder = os.path.join(mixed_folder, bundle_code)  # Folder for mixed bundles
            create_directory(bundle_folder)
            for product_code in product_codes:
                image_data = download_image(product_code)
                if image_data:
                    with open(os.path.join(bundle_folder, f"{product_code}.jpg"), 'wb') as file:
                        file.write(image_data)  # Save each product image
                else:
                    error_list.append((bundle_code, product_code))  # Log missing images
    
    # Save missing images list as CSV
    missing_images_df = pd.DataFrame(error_list, columns=["PZN Bundle", "PZN with image missing"])
    missing_images_path = "missing_images.csv"
    missing_images_df.to_csv(missing_images_path, index=False, sep=';')
    
    # Create a ZIP archive excluding missing images file
    shutil.make_archive(base_folder, 'zip', base_folder)
    
    with open("bundle_images.zip", "rb") as zip_file:
        return zip_file.read(), missing_images_df

# Streamlit UI
st.title("Bundle Image Downloader")
st.write("Upload a CSV file with bundle codes to download corresponding images.")

# File uploader widget
uploaded_file = st.file_uploader("Upload CSV File", type=["csv"])

# Process the uploaded file if available
if uploaded_file:
    with st.spinner("Processing..."):
        zip_data, missing_images_df = process_file(uploaded_file)
    st.success("Processing complete! Download your ZIP file below.")
    
    # Download button for the ZIP file
    st.download_button(label="📥 Download Images", data=zip_data, file_name="bundle_images.zip", mime="application/zip")
    
    # Display missing images if any
    if not missing_images_df.empty:
        st.warning("Some images were not found:")
        st.dataframe(missing_images_df.reset_index(drop=True))  # Display missing images list
        
        # Download button for missing images CSV
        st.download_button(label="📥 Download Missing Images CSV", data=open("missing_images.csv", "rb").read(), file_name="missing_images.csv", mime="text/csv")
