import streamlit as st
import os
import requests
import pandas as pd
import shutil
from io import BytesIO

# Streamlit UI
st.title("PDM Bundle Image Creator")

# Layout: Main content on the left, Product Image Preview on the right
col1, col2 = st.columns([2, 1])  # Column ratio: main content (2x) | preview (1x)

with col1:
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

with col2:
    # Product Image Preview section (now on the right)
    st.header("🔍 Product Image Preview")
    product_code = st.text_input("Enter Product Code:")
    image_type = st.selectbox("Select Image Type:", ["p1", "p10", "Custom"], index=0)
    custom_suffix = st.text_input("Custom Suffix (if selected)", "")

    if st.button("Preview Image") and product_code:
        suffix = custom_suffix if image_type == "Custom" else image_type
        image_url = f"https://cdn.shop-apotheke.com/images/{product_code}-{suffix}.jpg"
        response = requests.get(image_url, stream=True)
        if response.status_code == 200:
            st.image(image_url, caption=f"Preview: {product_code}-{suffix}.jpg")
            st.download_button("📥 Download Image", response.content, file_name=f"{product_code}-{suffix}.jpg", mime="image/jpeg")
        else:
            st.error("Image not found. Please check the product code and suffix.")
