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

        # Get the active case number from the JSON file
        st.session_state.case_number = get_active_case(f'{root_folder}')

        with st.sidebar:
            case_numbers = get_case_numbers(root_folder)
            # Display the selectbox only if there are case numbers
            if len(case_numbers) > 0 and st.session_state.case_number in case_numbers:
                st.session_state.case_number = st.selectbox("Case Number:", case_numbers, index=0 if 'case_number' not in st.session_state else case_numbers.index(st.session_state.case_number))

                # If the value of the selectbox changes, call the set_active_case function to update it in the JSON file
                if 'case_number' in st.session_state:
                    set_active_case(root_folder, st.session_state.case_number)
        
        
        existing_case_tab, new_case_tab = st.tabs(["Edit Case", "Add New Case"])
        
        with existing_case_tab:
            st.write("Update the details of the current case below:")
            with st.form(key='case_form'):

                # Display all the details of the case that we have stored
                # Get information necessary about the specific case
                case_number, which_side, party_names, timeline, actors, files, vectors = get_case_details(root_folder, st.session_state.case_number)
                print(f"👉 Case Number: {case_number} | Side: {which_side} | Parties: {party_names} | Timeline: {timeline} | Actors: {actors} | Files: {files} | Vectors: {vectors}")

                case_number_input = st.text_input("Case Number:", value=case_number, disabled=True)
                which_side_input = st.radio("Which side you Represent:", ["Defendant", "Plaintiff", "Petitioner", "Union of India"], index=["Defendant", "Plaintiff", "Petitioner", "Union of India"].index(which_side))
                party_names_input = st.text_input("Name(s) of the Party (Seperate with Commas):", value=party_names)
                submit_button = st.form_submit_button(label="Submit")

                if submit_button:
                    if put_case_details(root_folder, case_number_input, which_side_input, party_names_input, focus=True):
                        st.rerun()
            
            delete_button = st.button("🗑️ Delete Case")
            if delete_button:
                # Delete the case and refresh the page
                st.session_state.case_number = delete_case(root_folder, case_number)
                print(f"🗑️ Last Case: {st.session_state.case_number}")
                st.rerun()
                
                

        with new_case_tab:
            st.write("Add the details of a new case below:")
            with st.form(key='new_case_form'):
                #New case details to be provided by the user
                case_number_input = st.text_input("Case Number (Cannot be Edited Later):")
                which_side_input = st.radio("Who you Represent:", ["Defendant", "Plaintiff", "Petitioner", "Union of India"], index=0)
                party_names_input = st.text_input("Name(s) of the Party (Seperate with Commas):")
                submit_button = st.form_submit_button(label="Submit")
                
                if submit_button:
                    if put_case_details(root_folder, case_number_input, which_side_input, party_names_input, focus=True):
                        st.session_state.case_number = case_number_input
                        st.rerun()
    else:
        st.switch_page("pages/2 - Login.py")




if __name__ == '__main__':
    main()
