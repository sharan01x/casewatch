import utilities
from utilities import *

# For file management
def main():
    
    # Setup the UI
    st.set_page_config(page_title="Case Watch", page_icon="🏛️", layout="wide")

    # Authentication
    authenticator = verify_authentication()

    if st.session_state["authentication_status"]:

        new_files_tab, existing_files_tab = st.tabs(["Upload Files", "Existing Files"])
        root_folder = f'casefiles/{st.session_state["username"]}'
        main_folder = f'{root_folder}/main'
        background_folder = f'{root_folder}/background'

        with new_files_tab:
            st.header("Upload Files")
            with st.form(key='files_form', clear_on_submit=True, border=1):
                files = st.file_uploader("Choose files", type=["pdf", "txt"], accept_multiple_files=True, key="files_uploader")
                file_type = st.radio("Type of file you're uploading", ["Main Case Files", "Background Files"], index=0)
                if st.form_submit_button("Upload Files"):
                    with st.spinner("Processing..."):
                        if file_type == "Main Case Files":
                            store_files(main_folder, files)
                            existing_main_files = get_files_in_folder(main_folder)
                        else:
                            store_files(background_folder, files)
                            existing_background_files = get_files_in_folder(background_folder)
                    st.rerun()  # To refresh the page
        
        with existing_files_tab:

            st.header("Existing Files")
            with st.expander("Main Case Files", expanded=True):
                # Get the latest file list
                existing_main_files = get_files_in_folder(main_folder)
                if len(existing_main_files) == 0:
                    st.warning("No files uploaded yet", icon='⚠')
                else:
                    selected_files = []
                    for file in existing_main_files:
                        with st.container():
                            col1, col2 = st.columns([4, 1])
                            if col1.checkbox(file, key='main' + file):
                                selected_files.append(file)
                    if st.button('Delete Files', key="delete_main"):
                        for file in selected_files:
                            try:
                                os.remove(f'{main_folder}/{file}')
                                st.success("Deleted")
                            except FileNotFoundError:
                                st.error("Unable to delete")
                        existing_main_files = get_files_in_folder(main_folder)
                        store_files(main_folder, existing_main_files)
                        st.rerun()  # To refresh the page
            
            with st.expander("Background Files"):
                # Get the latest file list
                existing_background_files = get_files_in_folder(background_folder)
                if len(existing_background_files) == 0:
                    st.warning("No files uploaded yet", icon='⚠')
                else:
                    selected_files = []
                    for file in existing_background_files:
                        with st.container():
                            col1, col2 = st.columns([4, 1])
                            if col1.checkbox(file, key='background' + file):
                                selected_files.append(file)
                    if st.button('Delete Files', key="delete_background"):
                        for file in selected_files:
                            try:
                                os.remove(f'{background_folder}/{file}')
                                st.success("Deleted")
                            except FileNotFoundError:
                                st.error("Unable to delete")
                        existing_background_files = get_files_in_folder(background_folder)
                        store_files(background_folder, existing_background_files)
                        st.rerun()  # To refresh the page

    else:
        st.switch_page("pages/2 - Login.py")
    



if __name__ == '__main__':
    main()
