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
1. Create a **Quick Report** in Akeneo containing the list of products.
2. Select:
   - **CSV** format
   - **All Attributes** or **Grid Context** (ID & PZN included in set)
   - **With Codes**, **Without Media**
""")

# Function to clear old data
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
    try:
        st.experimental_rerun()
    except st.runtime.scriptrunner.RerunException:
        pass

# Sidebar Information
st.sidebar.header("🔹 What This App Does")
st.sidebar.markdown("""
- 📂 **Uploads a CSV file** containing bundle and product information.
- 🌐 **Downloads images** for each product from a specified URL.
- 🗂 **Organizes images** into folders based on the type of bundle.
- ❌ **Identifies missing images** and logs them separately.
- 📥 **Generates a ZIP file** containing all retrieved images.
- 🎨 **Automatically modifies images** in `bundle_2/` after processing.
""")

# Function to download an image for preview and processing
def download_image(product_code, extension):
    if product_code.startswith(('1', '0')):
        product_code = f"D{product_code}"
    
    url = f"https://cdn.shop-apotheke.com/images/{product_code}-p{extension}.jpg"
    response = requests.get(url, stream=True)
    
    if response.status_code == 200:
        return response.content, url
    return None, None

# Funzione per ritagliare automaticamente il bordo bianco
def trim(im):
    bg = Image.new(im.mode, im.size, (255, 255, 255))
    diff = ImageChops.difference(im, bg)
    bbox = diff.getbbox()
    return im.crop(bbox) if bbox else im

# Funzione per modificare le immagini in bundle_2
def modify_bundle_2_images():
    bundle_2_folder = os.path.join("bundle_images", "bundle_2")
    if not os.path.exists(bundle_2_folder):
        st.info("La cartella 'bundle_2' non esiste. Nessuna modifica applicata.")
        return

    st.info("🔄 Inizio modifica delle immagini in bundle_2...")
    for img_file in os.listdir(bundle_2_folder):
        img_path = os.path.join(bundle_2_folder, img_file)
        if not img_file.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        try:
            image = Image.open(img_path)

            # Ritaglia lo sfondo bianco
            image = trim(image)

            width, height = image.size
            merged_width = width * 2
            merged_height = height
            merged_image = Image.new("RGB", (merged_width, merged_height), (255, 255, 255))

            # Incolla due copie dell'immagine una accanto all'altra
            merged_image.paste(image, (0, 0))
            merged_image.paste(image, (width, 0))

            # Ridimensiona mantenendo le proporzioni, fino a un max di 1000x1000
            scale_factor = min(1000 / merged_width, 1000 / merged_height)
            new_size = (int(merged_width * scale_factor), int(merged_height * scale_factor))
            resized_image = merged_image.resize(new_size, Image.LANCZOS)

            # Crea una tela 1000x1000 e centra l'immagine ridimensionata
            final_image = Image.new("RGB", (1000, 1000), (255, 255, 255))
            x_offset = (1000 - new_size[0]) // 2
            y_offset = (1000 - new_size[1]) // 2
            final_image.paste(resized_image, (x_offset, y_offset))

            # Sovrascrive l'immagine originale
            final_image.save(img_path, "JPEG", quality=95)
            st.success(f"Modificata: {img_file}")
        except Exception as e:
            st.warning(f"Errore con {img_file}: {e}")
    st.success("🎉 Modifica di tutte le immagini in 'bundle_2' completata!")

# Funzione per processare il file CSV caricato
def process_file(uploaded_file):
    uploaded_file.seek(0)
    data = pd.read_csv(uploaded_file, delimiter=';', dtype=str)

    # Verifica colonne richieste
    required_columns = {'sku', 'pzns_in_set'}
    missing_columns = required_columns - set(data.columns)
    if missing_columns:
        st.error(f"Colonne mancanti: {', '.join(missing_columns)}")
        return None, None, None

    data = data[list(required_columns)]
    data.dropna(inplace=True)

    base_folder = "bundle_images"
    os.makedirs(base_folder, exist_ok=True)

    mixed_sets_needed = False
    mixed_folder = os.path.join(base_folder, "mixed_sets")
    error_list = []
    bundle_list = []

    for _, row in data.iterrows():
        bundle_code = row['sku'].strip()
        product_codes = row['pzns_in_set'].strip().split(',')
        num_products = len(product_codes)
        bundle_type = f"bundle of {num_products}"
        bundle_list.append([bundle_code, ', '.join(product_codes), bundle_type])

        if len(set(product_codes)) == 1:  # Bundle uniforme
            folder_name = os.path.join(base_folder, f"bundle_{num_products}")
            os.makedirs(folder_name, exist_ok=True)
            product_code = product_codes[0]
            image_data = download_image(product_code, "1")[0] or download_image(product_code, "10")[0]
            if image_data:
                image_path = os.path.join(folder_name, f"{bundle_code}-h1.jpg")
                with open(image_path, 'wb') as file:
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

    if not mixed_sets_needed and os.path.exists(mixed_folder):
        shutil.rmtree(mixed_folder)

    # Crea report delle immagini mancanti
    missing_images_df = pd.DataFrame(error_list, columns=["PZN Bundle", "PZN with image missing"])
    missing_images_csv = "missing_images.csv"
    missing_images_df.to_csv(missing_images_csv, index=False, sep=';')

    # Crea CSV con la lista dei bundle
    bundle_list_df = pd.DataFrame(bundle_list, columns=["sku", "pzns_in_set", "bundle type"])
    bundle_list_csv = "bundle_list.csv"
    bundle_list_df.to_csv(bundle_list_csv, index=False, sep=';')

    # Esegui la modifica delle immagini in bundle_2 (se esiste)
    modify_bundle_2_images()

    # Crea lo ZIP contenente tutte le immagini
    zip_path = "bundle_images.zip"
    shutil.make_archive("bundle_images_temp", 'zip', base_folder)
    os.rename("bundle_images_temp.zip", zip_path)

    with open(zip_path, "rb") as zip_file:
        return zip_file.read(), missing_images_df, bundle_list_df

# Sezione di anteprima immagine nella sidebar
st.sidebar.header("🔎 Product Image Preview")
product_code = st.sidebar.text_input("Enter Product Code:")
selected_extension = st.sidebar.selectbox("Select Image Extension:", [str(i) for i in range(1, 19)])

if st.sidebar.button("Show Image") and product_code:
    image_data, image_url = download_image(product_code, selected_extension)
    if image_data:
        image = Image.open(BytesIO(image_data))
        st.sidebar.image(image, caption=f"Product: {product_code} (p{selected_extension})", use_column_width=True)
        st.sidebar.download_button("📥 Download Image", data=image_data, file_name=f"{product_code}-p{selected_extension}.jpg", mime="image/jpeg")
    else:
        st.sidebar.error(f"⚠️ Nessuna immagine trovata per {product_code} con -p{selected_extension}.jpg")

# Caricamento file CSV
uploaded_file = st.file_uploader("Upload CSV File", type=["csv"])
if uploaded_file:
    with st.spinner("Processing..."):
        zip_data, missing_images_df, bundle_list_df = process_file(uploaded_file)
    if zip_data:
        st.success("✅ Processing complete! Download your files below.")
        st.download_button("📥 Download Bundle Images ZIP", zip_data, "bundle_images.zip", "application/zip")
        st.download_button("📥 Download Bundle List CSV", bundle_list_df.to_csv(sep=';', index=False), "bundle_list.csv", "text/csv")
        if not missing_images_df.empty:
            st.warning("Alcune immagini non sono state trovate:")
            st.dataframe(missing_images_df.reset_index(drop=True))
            st.download_button("📥 Download Missing Images CSV", missing_images_df.to_csv(sep=';', index=False).encode('utf-8'), "missing_images.csv", "text/csv")
