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

# Function to delete the previous bundle_images folder and other file outputs
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
    clear_old_data()  # Delete old files
    st.rerun()

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
- ❌ **Identifies missing images** and shows/logs them in a separate file.
- 📥 **Generates a ZIP file** containing all retrieved images.
- 📥 Generates a CSV file with a **list of Bundle** in the file.
- 🔎 **Tool Preview and download product images:** Useful when p1 or p10 images are missing or when the p1 image is of poor quality.
""")

# Product Image Preview Section con spinner posizionato accanto al tasto
st.sidebar.header("🔎 Product Image Preview")
product_code = st.sidebar.text_input("Enter Product Code:")
selected_extension = st.sidebar.selectbox("Select Image Extension:", [str(i) for i in range(1, 19)])

# Creiamo due colonne nella sidebar per posizionare il pulsante e lo spinner affiancati
with st.sidebar:
    col_button, col_spinner = st.columns([2, 1])
    show_image = col_button.button("Show Image")
    spinner_placeholder = col_spinner.empty()

if show_image and product_code:
    with spinner_placeholder:
        with st.spinner("Processing..."):
            image_data, image_url = download_image(product_code, selected_extension)
    if image_data:
        image = Image.open(BytesIO(image_data))
        st.sidebar.image(image, caption=f"Product: {product_code} (p{selected_extension})", use_container_width=True)
        st.sidebar.download_button(
            label="📥 Download Image",
            data=image_data,
            file_name=f"{product_code}-p{selected_extension}.jpg",
            mime="image/jpeg"
        )
    else:
        st.sidebar.error(f"⚠️ No image found for {product_code} with -p{selected_extension}.jpg")

# Function to download an image (usata anche in altre sezioni)
def download_image(product_code, extension):
    if product_code.startswith(('1', '0')):
        product_code = f"D{product_code}"
    url = f"https://cdn.shop-apotheke.com/images/{product_code}-p{extension}.jpg"
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        return response.content, url
    return None, None

# Function to trim white border from an image
def trim(im):
    bg = Image.new(im.mode, im.size, (255, 255, 255))  # White background
    diff = ImageChops.difference(im, bg)
    bbox = diff.getbbox()
    if bbox:
        return im.crop(bbox)
    return im  # Return original if no white border found

# Function to process double bundle image (for bundle_2)
def process_double_bundle_image(image):
    image = trim(image)
    width, height = image.size
    merged_width = width * 2
    merged_height = height
    merged_image = Image.new("RGB", (merged_width, merged_height), (255, 255, 255))
    merged_image.paste(image, (0, 0))
    merged_image.paste(image, (width, 0))
    scale_factor = min(1000 / merged_width, 1000 / merged_height)
    new_size = (int(merged_width * scale_factor), int(merged_height * scale_factor))
    resized_image = merged_image.resize(new_size, Image.LANCZOS)
    final_image = Image.new("RGB", (1000, 1000), (255, 255, 255))
    x_offset = (1000 - new_size[0]) // 2
    y_offset = (1000 - new_size[1]) // 2
    final_image.paste(resized_image, (x_offset, y_offset))
    return final_image

# Function to process triple bundle image (for bundle_3)
def process_triple_bundle_image(image):
    image = trim(image)
    width, height = image.size
    merged_width = width * 3
    merged_height = height
    merged_image = Image.new("RGB", (merged_width, merged_height), (255, 255, 255))
    merged_image.paste(image, (0, 0))
    merged_image.paste(image, (width, 0))
    merged_image.paste(image, (width * 2, 0))
    scale_factor = min(1000 / merged_width, 1000 / merged_height)
    new_size = (int(merged_width * scale_factor), int(merged_height * scale_factor))
    resized_image = merged_image.resize(new_size, Image.LANCZOS)
    final_image = Image.new("RGB", (1000, 1000), (255, 255, 255))
    x_offset = (1000 - new_size[0]) // 2
    y_offset = (1000 - new_size[1]) // 2
    final_image.paste(resized_image, (x_offset, y_offset))
    return final_image

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
    
    data = data[list(required_columns)]
    data.dropna(inplace=True)
    
    base_folder = "bundle_images"
    os.makedirs(base_folder, exist_ok=True)
    
    mixed_sets_needed = False  # Flag for eventual mixed bundles
    mixed_folder = os.path.join(base_folder, "mixed_sets")
    
    error_list = []  # List of tuples (bundle_code, product_code) for which image is missing
    bundle_list = []  # List to store bundle details

    for _, row in data.iterrows():
        bundle_code = row['sku'].strip()
        product_codes = [code.strip() for code in row['pzns_in_set'].strip().split(',')]
        num_products = len(product_codes)
        
        # Se tutti i pzns sono uguali, il bundle è uniforme, altrimenti è "mixed"
        if len(set(product_codes)) == 1:
            bundle_type = f"bundle of {num_products}"
        else:
            bundle_type = "mixed"
        bundle_list.append([bundle_code, ', '.join(product_codes), bundle_type])

        if len(set(product_codes)) == 1:  # Bundle uniforme
            folder_name = f"{base_folder}/bundle_{num_products}"
            os.makedirs(folder_name, exist_ok=True)
            product_code = product_codes[0]
            image_data = download_image(product_code, "1")[0] or download_image(product_code, "10")[0]
            
            if image_data:
                try:
                    img = Image.open(BytesIO(image_data))
                    # Se il bundle contiene 2 prodotti, applica la trasformazione per bundle_2
                    if num_products == 2:
                        final_img = process_double_bundle_image(img)
                    # Se il bundle contiene 3 prodotti, applica la trasformazione per bundle_3
                    elif num_products == 3:
                        final_img = process_triple_bundle_image(img)
                    else:
                        final_img = img  # Nessuna trasformazione per altri casi uniformi
                    final_img.save(os.path.join(folder_name, f"{bundle_code}-h1.jpg"), "JPEG", quality=95)
                except Exception as e:
                    st.error(f"Error processing image for bundle {bundle_code}: {e}")
                    error_list.append((bundle_code, product_code))
            else:
                error_list.append((bundle_code, product_code))
        else:  # Bundle misto
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
    
    # Rimuove la cartella mixed_sets se non ci sono bundle misti
    if not mixed_sets_needed and os.path.exists(mixed_folder):
        shutil.rmtree(mixed_folder)

    # Aggrega le PZN mancanti per bundle in un'unica cella, separate da virgola
    if error_list:
        missing_images_df = pd.DataFrame(error_list, columns=["PZN Bundle", "PZN with image missing"])
        missing_images_df = missing_images_df.groupby("PZN Bundle", as_index=False).agg({
            "PZN with image missing": lambda x: ', '.join(x)
        })
    else:
        missing_images_df = pd.DataFrame(columns=["PZN Bundle", "PZN with image missing"])
    
    missing_images_csv = "missing_images.csv"
    missing_images_df.to_csv(missing_images_csv, index=False, sep=';')
    with open(missing_images_csv, "rb") as f:
        missing_images_data = f.read()

    # Crea il CSV della lista dei bundle
    bundle_list_df = pd.DataFrame(bundle_list, columns=["sku", "pzns_in_set", "bundle type"])
    bundle_list_csv = "bundle_list.csv"
    bundle_list_df.to_csv(bundle_list_csv, index=False, sep=';')
    with open(bundle_list_csv, "rb") as f:
        bundle_list_data = f.read()

    # Crea il file ZIP delle immagini
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
