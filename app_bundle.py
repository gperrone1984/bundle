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
""")

# Product Image Preview Section
st.sidebar.header("🔎 Product Image Preview")
product_code = st.sidebar.text_input("Enter Product Code:")
selected_extension = st.sidebar.selectbox("Select Image Extension:", ["1", "10"])

def download_image(product_code, extension):
    if product_code.startswith(('1', '0')):
        product_code = f"D{product_code}"
    url = f"https://cdn.shop-apotheke.com/images/{product_code}-p{extension}.jpg"
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        return response.content
    return None

if st.sidebar.button("Show Image") and product_code:
    image_data = download_image(product_code, selected_extension)
    if image_data:
        image = Image.open(BytesIO(image_data))
        st.sidebar.image(image, caption=f"Product: {product_code} (p{selected_extension})", use_column_width=True)
        st.sidebar.download_button(
            label="📥 Download Image",
            data=image_data,
            file_name=f"{product_code}-p{selected_extension}.jpg",
            mime="image/jpeg"
        )
    else:
        st.sidebar.error(f"⚠️ No image found for {product_code} with -p{selected_extension}.jpg")

# Function to process images for bundles of 2 (duplicate side by side)
def create_double_bundle_image(img):
    img = ImageChops.invert(ImageChops.difference(img, Image.new(img.mode, img.size, img.getpixel((0, 0)))))
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    new_width = img.width * 2
    new_height = img.height
    combined_img = Image.new("RGB", (new_width, new_height), (255, 255, 255))
    combined_img.paste(img, (0, 0))
    combined_img.paste(img, (img.width, 0))
    final_img = Image.new("RGB", (1000, 1000), (255, 255, 255))
    x_offset = (1000 - new_width) // 2
    y_offset = (1000 - new_height) // 2
    final_img.paste(combined_img, (x_offset, y_offset))
    return final_img

# Function to process the uploaded CSV file
def process_file(uploaded_file):
    uploaded_file.seek(0)
    data = pd.read_csv(uploaded_file, delimiter=';', dtype=str)
    required_columns = {'sku', 'pzns_in_set'}
    if not required_columns.issubset(set(data.columns)):
        st.error("Missing required columns in CSV file.")
        return None, None, None, None
    data.dropna(inplace=True)
    base_folder = "bundle_images"
    os.makedirs(base_folder, exist_ok=True)
    bundle_list = []
    error_list = []
    for _, row in data.iterrows():
        bundle_code = row['sku'].strip()
        product_codes = row['pzns_in_set'].strip().split(',')
        num_products = len(product_codes)
        bundle_list.append([bundle_code, ', '.join(product_codes), f"bundle of {num_products}"])
        if len(set(product_codes)) == 1 and num_products == 2:
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
    return base_folder, bundle_list, error_list

uploaded_file = st.file_uploader("Upload CSV File", type=["csv"])
if uploaded_file:
    with st.spinner("Processing..."):
        base_folder, bundle_list, error_list = process_file(uploaded_file)
    st.success("**Processing complete! Download your files below.**")
    shutil.make_archive("bundle_images", 'zip', base_folder)
    with open("bundle_images.zip", "rb") as f:
        st.download_button("📥 Download Images", data=f, file_name="bundle_images.zip", mime="application/zip")
    bundle_list_df = pd.DataFrame(bundle_list, columns=["sku", "pzns_in_set", "bundle type"])
    bundle_list_csv = "bundle_list.csv"
    bundle_list_df.to_csv(bundle_list_csv, index=False, sep=';')
    with open(bundle_list_csv, "rb") as f:
        st.download_button("📥 Download Bundle List", data=f, file_name="bundle_list.csv", mime="text/csv")
