import utilities
from utilities import *

# For file management
def main():
    
    # Setup the UI
    st.set_page_config(page_title="Case Watch", page_icon="🏛️", layout="wide")

    # Authentication
    authenticator = verify_authentication()

    if st.session_state["authentication_status"]:

        root_folder = f'casefiles/{st.session_state["username"]}'

        # Get the active case number from the JSON file
        st.session_state.case_number = get_active_case(f'{root_folder}')

        if st.session_state.case_number is not None:

            with st.sidebar:
                case_numbers = get_case_numbers(root_folder)
                # Display the selectbox only if there are case numbers
                if len(case_numbers) > 0 and st.session_state.case_number in case_numbers:
                    st.session_state.case_number = st.selectbox("Case Number:", case_numbers, index=0 if 'case_number' not in st.session_state else case_numbers.index(st.session_state.case_number))

                    # If the value of the selectbox changes, call the set_active_case function to update it in the JSON file
                    if 'case_number' in st.session_state:
                        set_active_case(root_folder, st.session_state.case_number)

            st.header("File Management")
            existing_files, upload_files = st.tabs(["Existing Files", "Upload New Files"])

            with upload_files:
                st.write("Please add more files associated with this case below:")
                with st.form(key='files_form', clear_on_submit=True, border=1):
                    files = st.file_uploader("Choose files", type=["pdf", "txt"], accept_multiple_files=True, key="files_uploader")
                    if st.form_submit_button("Upload Files"):
                        with st.spinner("Processing..."):
                            store_files(root_folder, files)
                            existing_main_files = get_files(root_folder)
                        st.rerun()  # To refresh the page
                
            with existing_files:    
                st.write("The following files are associated with this case:")
                # Get the latest file list
                existing_main_files = get_files(root_folder)
                
                if len(existing_main_files) == 0:
                    st.warning("No files uploaded yet", icon='⚠')
                else:
                    selected_files = []
                    for file in existing_main_files:
                        with st.container():
                            col1, col2 = st.columns([4, 1])
                            if col1.checkbox(file, key='main' + file):
                                selected_files.append(file)
                    if st.button('🗑️ Delete Files', key="delete_main"):
                        with st.spinner("Deleting..."):
                            delete_files(root_folder, selected_files)
                        existing_main_files = get_files(root_folder)
                        st.rerun()  # To refresh the page
        else:
            # No case number found in the JSON file, redirect to the Case Details page
            st.warning("No details of the case is on file. Please provide the necessary information by choosing Case Details in the sidebar to get started.")
            if st.button("Go to Case Details"):
                st.switch_page("pages/6 - Case Details.py")

    else:
        st.switch_page("pages/2 - Login.py")
    



if __name__ == '__main__':
    main()
