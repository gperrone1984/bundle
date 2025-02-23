if uploaded_file:
    cols = st.columns([2, 1, 1, 1])
    with cols[0]:
        if st.button("Process CSV"):
            start_time = time.time()  # Start timer
            progress_bar = st.progress(0)
            zip_data, missing_images_data, missing_images_df, bundle_list_data = process_file(uploaded_file, progress_bar)
            progress_bar.empty()
            elapsed_time = time.time() - start_time
            minutes = int(elapsed_time // 60)
            seconds = int(elapsed_time % 60)
            st.write(f"Time to download and process images: {minutes}:{seconds:02d} minutes")
            if zip_data:
                st.session_state["zip_data"] = zip_data
                st.session_state["bundle_list_data"] = bundle_list_data
                st.session_state["missing_images_data"] = missing_images_data
                st.session_state["missing_images_df"] = missing_images_df
    with cols[1]:
        st.markdown("**Cross-country photos:**")
    with cols[2]:
        if st.button("FR", key="fr_button_main"):
            st.session_state["fallback_ext"] = "1-fr"
    with cols[3]:
        if st.button("DE", key="de_button_main"):
            st.session_state["fallback_ext"] = "1-de"
