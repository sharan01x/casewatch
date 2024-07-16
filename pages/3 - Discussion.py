# import utilities
from utilities import *

authenticator = verify_authentication()

# Main application function adjustments
def main():
    
    if st.session_state["authentication_status"]:
        
        st.header("Discussion")

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
        

        if st.session_state.case_number is not None:
            
            # A case number has been selected, but check if the other details are present, if not get them
            if 'which_side' not in st.session_state or 'party_names' not in st.session_state or 'timeline' not in st.session_state or 'actors' not in st.session_state or 'files' not in st.session_state:
                # Get information necessary about the specific case
                case_number, which_side, party_names, timeline, actors, files, focus = get_case_details(root_folder, st.session_state.case_number)
                
                print(f"Case Number: {case_number} | Side: {which_side} | Parties: {party_names} | Timeline: {timeline} | Actors: {actors} | Files: {files} | Focus: {focus}")

            # Get the latest file list
            existing_main_files = get_files(root_folder)

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
                        response = get_response(f'{root_folder}/{case_number}/vectors', user_query, which_side, party_names)
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
            st.warning("No details of the case is on file. Please provide the necessary information by choosing Case Details in the sidebar to get started.")
            if st.button("Go to Case Details"):
                st.switch_page("pages/6 - Case Details.py")

    else:
        st.switch_page("pages/2 - Login.py")

                




if __name__ == '__main__':
    main()
