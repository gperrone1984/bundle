#sembra funzionare, non c´é piú il tasto clear ma non sembra convervare i dati


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
- ❓ This app automates the **creation of product bundles** by **downloading and organizing product images**
- 📂 **Uploads a CSV file** containing bundle and product information.
- 🌐 **Downloads images** for each product from a specified URL..
- 🔎 **Searches** first for the manufacturer image (p1), then the Fotobox image (p10).
- 🗂 **Organizes images** into folders based on the type of bundle.
- ✏️ **Renames images** for bundles double, triple etc. using the bundle code.
- 📁 **Sorts mixed-set images** into separate folders named after the bundle code.
- ❌ **Identifies missing images** and show/logs them in a separate file.
- 📥 **Generates a ZIP file** containing all retrieved images.
- 📥 Generates a CSV file with a **list of Bundle** in the file.
- 🔎 **Tool Preview and download product images:**Useful when p1 or p10 images are missing or when the p1 image is of poor quality.
""")

# Product Image Preview Section (RESTORED)
st.sidebar.header("🔎 Product Image Preview")
product_code = st.sidebar.text_input("Enter Product Code:")
selected_extension = st.sidebar.selectbox("Select Image Extension:", [str(i) for i in range(1, 19)])

# Function to download an image for preview
def download_image(product_code, extension):
    if product_code.startswith(('1', '0')):
        product_code = f"D{product_code}"
    
    url = f"https://cdn.shop-apotheke.com/images/{product_code}-p{extension}.jpg"
    response = requests.get(url, stream=True)
    
    if response.status_code == 200:
        return response.content, url
    return None, None

# Display image preview (RESTORED)
if st.sidebar.button("Show Image") and product_code:
    image_data, image_url = download_image(product_code, selected_extension)
    
    if image_data:
        image = Image.open(BytesIO(image_data))
        st.sidebar.image(image, caption=f"Product: {product_code} (p{selected_extension})", use_container_width=True)
        
        # Download button for the image
        st.sidebar.download_button(
            label="📥 Download Image",
            data=image_data,
            file_name=f"{product_code}-p{selected_extension}.jpg",
            mime="image/jpeg"
        )
    else:
        st.sidebar.error(f"⚠️ No image found for {product_code} with -p{selected_extension}.jpg")

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
    os.makedirs(base_folder, exist_ok=True)
    
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
            os.makedirs(folder_name, exist_ok=True)
            product_code = product_codes[0]
            image_data = download_image(product_code, "1")[0] or download_image(product_code, "10")[0]  # Try p1, then p10
            
            if image_data:
                with open(os.path.join(folder_name, f"{bundle_code}-h1.jpg"), 'wb') as file:
                    file.write(image_data)
            else:
                error_list.append((bundle_code, product_code))
        else:  # Mixed bundle
            mixed_sets_needed = True
            bundle_folder = os.path.join(mixed_folder, bundle_code)
            os.makedirs(bundle_folder, exist_ok=True)
            for product_code in product_codes:
                image_data = download_image(product_code, "1")[0] or download_image(product_code, "10")[0]
                
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
        st.download_button(label="📥 **Download Images for Bundle Creation**", data=zip_data, file_name="bundle_images.zip", mime="application/zip")
        st.download_button(label="📥 Download Bundle List", data=bundle_list_data, file_name="bundle_list.csv", mime="text/csv")
        
        if missing_images_df is not None and not missing_images_df.empty:
            st.warning("**Some images were not found:**")
            st.dataframe(missing_images_df.reset_index(drop=True))
            st.download_button(label="📥 Download Missing Images CSV", data=missing_images_data, file_name="missing_images.csv", mime="text/csv")
