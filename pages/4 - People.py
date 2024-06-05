import utilities
from utilities import *

# For file management
def main():
    
    # Setup the UI
    st.set_page_config(page_title="Case Watch", page_icon="🏛️", layout="wide")

    authenticator = verify_authentication()

    if st.session_state["authentication_status"]:

        vectors_folder = f'casefiles/{st.session_state["username"]}/vectors'
        actors_file = f'casefiles/{st.session_state["username"]}/actors.md'

        st.header("People Involved")
        response = get_actors(vectors_folder, actors_file, False)
        col1, col2 = st.columns([4, 1])
        
        with col1:
            with st.container(border=1):
                st.markdown(response)
        with col2:
            if st.button("🔄 Refresh List", key="refresh_actors"):
                response = get_actors(vectors_folder, actors_file, True)
                st.rerun()
            
            if st.button("🖨️ Print List (Soon)", key="print_actors"):
                pass
    else:
        st.switch_page("pages/2 - Login.py")




if __name__ == '__main__':
    main()
