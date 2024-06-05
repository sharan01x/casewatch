# import utilities
from utilities import *

authenticator = verify_authentication()

# Main application function adjustments
def main():
    
    if st.session_state["authentication_status"]:
        
        st.header("Discussion")

        root_folder = f'casefiles/{st.session_state["username"]}'

         # Get information necessary to get started
        case_number, which_side, party_names = get_case_details(root_folder)
        print(f"Case Number: {case_number}, Which Side: {which_side}, Party Names: {party_names}")

        if case_number is None:
            st.warning("No details of the case present. Please provide the case details in the sidebar to get started.")
            return
        else:

            # Get the latest file list
            existing_main_files = get_files_in_folder(f'{root_folder}/main')

            if existing_main_files is None or len(existing_main_files) == 0:
                st.info("In order for me to start helping you with this case, please upload some case files in the Files section.")
            else:
                #Get the history of the chat, but make sure Streamlit doesn't reset it every time
                if "messages" not in st.session_state:
                    st.session_state.messages = []
                else:

                    # Display the chat messages so far
                    for i, message in enumerate(st.session_state.messages):
                        if isinstance(message, AIMessage):
                            with st.chat_message("AI"):
                                st.markdown(message.content)

                                with st.expander("Follow-up:", expanded=False):
                                    if st.button("Case Laws", key=f"case_laws_{i}", help="Get the case laws related to this point"):
                                        case_laws = get_case_laws(which_side, party_names)
                                        st.session_state.messages.append(case_laws)
                                    if st.button("Opposing Arguments", key=f"opposing_{i}", help="Get what the opposition could argue regarding this point"):
                                        opposition_arguments = get_opposition_arguments(which_side, party_names)
                                        st.session_state.messages.append(opposition_arguments)
                                    if st.button("Unsubstantiated Points", key=f"unsubstantiated_{i}", help="Get the points that haven't been proven yet regarding this point"):
                                        pass

                        elif isinstance(message, HumanMessage):
                            with st.chat_message("Human"):
                                st.markdown(message.content)
                
                # User input
                user_query = st.chat_input("Type your message here...")

                if user_query:
                    # Append the query to displayed messages
                    st.session_state.messages.append(HumanMessage(content=user_query))

                    # Append the query to chat history list
                    chat_history.add_message(HumanMessage(content=user_query))
                    
                    # Display a temporary "processing" message
                    processing_message = st.empty()
                    processing_message.text("Processing...")
                    
                    # Generate response using conversation chains
                    try:
                        response = get_response(f'{root_folder}/vectors', user_query, which_side, party_names)
                        print(f"✅ Response: {response}")

                        # Append the response to chat history
                        chat_history.add_message(response)

                        #Display the message
                        st.session_state.messages.append(AIMessage(role="AI", content=response.content))
                        st.rerun()

                        
                        
                    except Exception as ex:
                        st.error(f"Error generating response: {ex}")

                    # Remove the "processing" message
                    processing_message.empty()

    else:
        st.switch_page("pages/2 - Login.py")

                




if __name__ == '__main__':
    main()
