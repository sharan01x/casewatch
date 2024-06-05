import utilities
from utilities import *

# For file management
def main():
    
    # Setup the UI
    st.set_page_config(page_title="Case Watch", page_icon="🏛️", layout="wide")

    authenticator = verify_authentication()

    if st.session_state["authentication_status"]:

        st.header("Case Details")
        root_folder = f'casefiles/{st.session_state["username"]}'

        # Get information necessary to get started
        case_number, which_side, party_names = get_case_details(root_folder)
        
        col1, col2 = st.columns([4, 1])
        
        with col1:
            with st.form(key='case_form'):
                case_number = st.text_input("Case Number:", value=case_number)
                which_side = st.radio("Who you Represent:", ["Defendant", "Plaintiff", "Petitioner", "Union of India"], index=0 if which_side == "Defendant" else 0)
                party_names = st.text_input("Name(s) of the Party:", value=party_names)
                submit_button = st.form_submit_button(label="Submit")
                if submit_button:
                    put_case_details(root_folder, case_number, which_side, party_names)

        with col2:
            pass
    else:
        st.switch_page("pages/2 - Login.py")




if __name__ == '__main__':
    main()
