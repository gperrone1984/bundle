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
    clear_old_data()
    st.rerun()

# Function to download an image for preview or processing
def download_image(product_code, extension):
    if product_code.startswith(('1', '0')):
        product_code = f"D{product_code}"
    
    url = f"https://cdn.shop-apotheke.com/images/{product_code}-p{extension}.jpg"
    response = requests.get(url, stream=True)
    
    if response.status_code == 200:
        return response.content
    return None

# Function to trim white borders
def trim_white_borders(img):
    bg = Image.new(img.mode, img.size, img.getpixel((0, 0)))
    diff = ImageChops.difference(img, bg)
    bbox = diff.getbbox()
    if bbox:
        return img.crop(bbox)
    return img

# Function to process images for bundles of 2 (duplicate side by side)
def create_double_bundle_image(img):
    img = trim_white_borders(img)  # Remove white borders
    
    # Create a new image (double width, same height)
    new_width = img.width * 2
    new_height = img.height
    combined_img = Image.new("RGB", (new_width, new_height), (255, 255, 255))
    combined_img.paste(img, (0, 0))
    combined_img.paste(img, (img.width, 0))
    
    # Center in a 1000x1000 white canvas
    final_img = Image.new("RGB", (1000, 1000), (255, 255, 255))
    x_offset = (1000 - new_width) // 2
    y_offset = (1000 - new_height) // 2
    final_img.paste(combined_img, (x_offset, y_offset))
    
    return final_img

# Function to process the uploaded CSV file
def process_file(uploaded_file):
    uploaded_file.seek(0)  # Reset file pointer to ensure fresh read
    data = pd.read_csv(uploaded_file, delimiter=';', dtype=str)
    
    required_columns = {'sku', 'pzns_in_set'}
    if not required_columns.issubset(set(data.columns)):
        st.error("Missing required columns in CSV file.")
        return None, None, None, None
    
    data.dropna(inplace=True)
    base_folder = "bundle_images"
    os.makedirs(base_folder, exist_ok=True)
    error_list = []
    bundle_list = []
    
    for _, row in data.iterrows():
        bundle_code = row['sku'].strip()
        product_codes = row['pzns_in_set'].strip().split(',')
        
        num_products = len(product_codes)
        bundle_list.append([bundle_code, ', '.join(product_codes), f"bundle of {num_products}"])
        
        if len(set(product_codes)) == 1 and num_products == 2:  # Bundle of 2, same product
            folder_name = f"{base_folder}/bundle_2"
            os.makedirs(folder_name, exist_ok=True)
            product_code = product_codes[0]
            image_data = download_image(product_code, "1") or download_image(product_code, "10")
            
            if image_data:
                img = Image.open(BytesIO(image_data)).convert("RGB")
                final_img = create_double_bundle_image(img)
                output_path = os.path.join(folder_name, f"{bundle_code}-h1.jpg")
                final_img.save(output_path, "JPEG", quality=95)
            else:
                error_list.append((bundle_code, product_code))
    
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
        st.download_button("📥 **Download Images**", data=zip_data, file_name="bundle_images.zip", mime="application/zip")
