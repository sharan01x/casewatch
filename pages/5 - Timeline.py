import utilities
from utilities import *

# For file management
def main():
    
    # Setup the UI
    st.set_page_config(page_title="Case Watch", page_icon="🏛️", layout="wide")

    authenticator = verify_authentication()

    if st.session_state["authentication_status"]:

        root_folder = f'casefiles/{st.session_state["username"]}'
        st.session_state.case_number = get_active_case(f'{root_folder}')
       
        st.header("Timeline of Events")
        response = get_timeline(root_folder, refresh=False)

        with st.sidebar:
            case_numbers = get_case_numbers(root_folder)
            # Display the selectbox only if there are case numbers
            if len(case_numbers) > 0 and st.session_state.case_number in case_numbers:
                st.session_state.case_number = st.selectbox("Case Number:", case_numbers, index=0 if 'case_number' not in st.session_state else case_numbers.index(st.session_state.case_number))

                # If the value of the selectbox changes, call the set_active_case function to update it in the JSON file
                if 'case_number' in st.session_state:
                    set_active_case(root_folder, st.session_state.case_number)
        
        col1, col2 = st.columns([4, 1])
        
        with col1:
            st.write("These are the important dates and events associated with the case listed in reverse chronological order. You can refresh the list, delete it, or print it.")
            with st.container(border=1):
                st.markdown(response)
        with col2:
            if st.button("🔄 Refresh List", key="refresh_timeline"):
                response = get_timeline(root_folder, refresh=True)
            
            if st.button("🗑️ Delete Timeline", key="delete_timeline"):
                with st.spinner("Deleting..."):
                    if delete_timeline(root_folder):
                        st.rerun()

            if st.button("🖨️ Print List (Soon)", key="print_actors"):
                pass
    else:
        st.switch_page("pages/2 - Login.py")



if __name__ == '__main__':
    main()
