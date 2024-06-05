import os
import yaml
import streamlit as st
from yaml.loader import SafeLoader
from dotenv import load_dotenv
import streamlit_authenticator as stauth

#Set up the environment
load_dotenv()

USER_CONFIG_FILE = os.getenv("USER_CONFIG_FILE")

def main():
    # Setup the UI
    st.set_page_config(page_title="Case Watch", page_icon="🏛️", layout="centered")

    # Authentication
    with open(USER_CONFIG_FILE, "r") as f:
        config = yaml.load(f, Loader=SafeLoader)

    authenticator = stauth.Authenticate(
        config["credentials"],
        config['cookie']['name'],
        config['cookie']['key'],
        config['cookie']['expiry_days'],
        config['pre-authorized']
    )

    if not st.session_state["authentication_status"]:

        # Create two tabs
        login_tab, register_tab = st.tabs(["Login", "New User Registration"])
        with login_tab:
            st.markdown("Registered users can login below. If you haven't registered yet, please click on the 'New User Registration' tab above to register.")
            authenticator.login(fields={'Form name': 'Login', 'Login': 'Submit'},)

            if st.session_state["authentication_status"]:
                st.switch_page("pages/3 - Discussion.py")
            elif st.session_state["authentication_status"] is False:
                st.error("The user name or password is incorrect or you need to log in again")
            elif st.session_state["authentication_status"] is None:
                st.warning("This application is only available by invitation. If you'd like to request an invitation, please write to casewatch@redd.in")
        with register_tab:
            # Register user form code goes here
            st.markdown("Please register below using the email address where you've received an invitation. If you would like to request an invitation, please write to casewatch@redd.in.")
            try:
                email_of_registered_user, username_of_registered_user, name_of_registered_user = authenticator.register_user(fields={'Form name': 'Register', 'Register': 'Submit'}, pre_authorization=False)
                if email_of_registered_user:
                    st.success('User registered successfully')
            except Exception as e:
                st.error(e)
    else:
        st.switch_page("pages/3 - Discussion.py")

    

if __name__ == '__main__':
    main()