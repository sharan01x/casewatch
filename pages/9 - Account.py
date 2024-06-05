import utilities
from utilities import *

# For file management
def main():
    
    # Setup the UI
    st.set_page_config(page_title="Case Watch", page_icon="🏛️", layout="wide")

    # Authentication
    authenticator = verify_authentication()

    st.header("Account Details")
    # Update user details
    if st.session_state["authentication_status"]:
    
        col1, col2 = st.columns([4, 1])
        
        with col1:
            
            try:
                if authenticator.update_user_details(st.session_state["username"], fields={"Form name": "Update your information", "Update": "Submit"}, clear_on_submit=True):
                    update_user_config_file(config)
            except Exception as e:
                st.write("There was an error updating the user details. Please review your details and try again.")
                print(f"❌ Error updating user details: {e}")

            
            try:
                if authenticator.reset_password(st.session_state["username"], fields={"Form name": "Update your password", "Update": "Submit"}, clear_on_submit=True):
                    update_user_config_file(config)
            except Exception as e:
                st.write("There was an error updating the password. Please review your details and try again.")
                print(f"❌ Error updating password: {e}")     
        
        with col2:
            authenticator.logout()
    else:
        st.switch_page("pages/2 - Login.py")





if __name__ == '__main__':
    main()
