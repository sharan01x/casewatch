       
# Standard Python libraries
import os
import fnmatch
import json
import yaml
import pandas as pd
import streamlit as st
import streamlit_authenticator as stauth
import shutil

from yaml.loader import SafeLoader
from datetime import datetime
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_community.document_loaders import PyPDFDirectoryLoader, PyPDFLoader, PyPDFium2Loader
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain.schema.document import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from dateutil.parser import parse



#Set up the environment
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDINGS_MODEL = os.getenv("EMBEDDINGS_MODEL")
USER_CONFIG_FILE = os.getenv("USER_CONFIG_FILE")

# LLM provider: defaults to local Ollama (OpenAI-compatible endpoint)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "qwen3.8:27b-mlx")
OLLAMA_ECO_MODEL = os.getenv("OLLAMA_ECO_MODEL", "qwen3.8:27b-mlx")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "qwen3-embedding:latest")

# For main operations
llm = ChatOpenAI(
    openai_api_key="ollama",  # Ollama ignores the key but OpenAI client requires one
    model_name=OLLAMA_CHAT_MODEL,
    temperature=0.3,
    base_url=OLLAMA_BASE_URL,
)
llm_eco = ChatOpenAI(
    openai_api_key="ollama",
    model_name=OLLAMA_ECO_MODEL,
    temperature=0.3,
    base_url=OLLAMA_BASE_URL,
)
embeddings = OpenAIEmbeddings(
    model=OLLAMA_EMBED_MODEL,
    api_key="ollama",
    base_url=OLLAMA_BASE_URL,
    check_embedding_ctx_length=False,
)
vector_store = None


# Initialize the chat history
chat_history = ChatMessageHistory()

# SUPPORTING FUNCTIONS ////////////////////////





def verify_authentication():
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

    return authenticator






# Write the user configuration to a file
def update_user_config_file(config):
    try:
        with open(USER_CONFIG_FILE, 'w') as file:
            yaml.dump(config, file, default_flow_style=False)
            print(f"✅ User configuration file updated")
    except Exception as e:
        raise Exception(f"Error updating user configuration file: {e}")






# Write the case details to the JSON file
def put_case_details(root_folder, case_number, which_side=None, party_names=None, timeline=None, actors=None, files=None, vectors=None, focus=None):
    case_details_file = f'{root_folder}/case_details.json'

    # Read the file and see if the case number already exists
    # If the case number exists, update the details
    # If the case number doesn't exist, add a new case node and then the details as sub-nodes

    if not os.path.exists(case_details_file):
        #Create the file with the empty JSON object
        with open(case_details_file, 'w') as f:
            f.write('{"cases": {}}')

    with open(case_details_file, 'r') as f:
        cases_list = json.load(f)

    if case_number in cases_list['cases']:
        # The following allows for selective updating of the case details
        if which_side is not None:
            cases_list['cases'][case_number]['which_side'] = which_side
        if party_names is not None:
            cases_list['cases'][case_number]['party_names'] = party_names
        if timeline is not None:
            cases_list['cases'][case_number]['timeline'] = timeline
        if actors is not None:
            cases_list['cases'][case_number]['actors'] = actors
        if files is not None:
            cases_list['cases'][case_number]['files'] = files
        if vectors is not None:
            cases_list['cases'][case_number]['vectors'] = vectors
        if focus is not None:
            cases_list['cases'][case_number]['focus'] = focus

    else:
        cases_list['cases'][case_number] = {
            'which_side': which_side,
            'party_names': party_names,
            'timeline': timeline,
            'actors': actors,
            'files': files,
            'vectors': vectors,
            'focus': focus
        }

    with open(case_details_file, 'w') as f:
        json.dump(cases_list, f)

    return True






# Read the case details from a file if it exists
def get_case_details(root_folder, case_number=None):
    case_details_file = f'{root_folder}/case_details.json'
    
    #Check if the file exists, if it does, read the JSON object from the file
    #If it doesn't exist, create an empty file
    #Read the JSON object from the file and return the values
    
    
    if not os.path.exists(case_details_file):
        #Create the file with the empty JSON object
        with open(case_details_file, 'w') as f:
            f.write('{"cases": {}}')
    
    #Read the file
    with open(case_details_file, 'r') as f:
        cases_list = json.load(f)

        # If there's more than zero cases in the JSON object, then get the details of the case_number
        if len(cases_list['cases']) > 0:
        
            # If no case number was provided, then we get the case number from the JSON object where the node 'focus' is true
            # If there is no case marked as focus, then we get the last case number
            if case_number == None:
                
                case_number = next((key for key, value in cases_list['cases'].items() if value.get('focus', False)), None)
                if case_number == None:
                    case_number = list(cases_list['cases'].keys())[-1]

            #Get which_side, party_names from the JSON object which matches the case_number
            which_side = cases_list['cases'][case_number]['which_side']
            party_names = cases_list['cases'][case_number]['party_names']
            timeline = cases_list['cases'][case_number]['timeline']
            actors = cases_list['cases'][case_number]['actors']
            files = cases_list['cases'][case_number]['files']
            focus = cases_list['cases'][case_number]['focus']

            return case_number, which_side, party_names, timeline, actors, files, focus
            
        else:
            # There are no cases in the JSON object
            return None, None, None, None, None, None, None








# Delete a case
def delete_case(root_folder, case_number):
    case_details_file = f'{root_folder}/case_details.json'

    # Read the file and find all the files in the files node of the case_number
    # Delete the files from the 'casefiles' directory
    # Delete the vectors from the 'vectors' directory
    # Delete the case_number node from the JSON object
    # Set the focus node of the last case to true if there's at least one case
    # Write the JSON object back to the file

    with open(case_details_file, 'r') as f:
        cases_list = json.load(f)
    
    if case_number in cases_list['cases']:

        # Delete the folder and all its contents which will get rid of vectors and the files
        if os.path.exists(f'{root_folder}/{case_number}'):
            shutil.rmtree(f'{root_folder}/{case_number}')

        # Delete the case_number node from the JSON object
        del cases_list['cases'][case_number]

        # Set the focus node of the last case to true if there's at least one case remaining
        if len(cases_list['cases']) > 0:
            last_case = list(cases_list['cases'].keys())[-1]
            cases_list['cases'][last_case]['focus'] = True

        # Write the JSON object back to the file
        with open(case_details_file, 'w') as f:
            json.dump(cases_list, f)


    # If there was a value assigned ot last_case, return it
    if 'last_case' != None:
        return last_case
    else:
        return None








# Set the active case to a particular one
def set_active_case(root_folder, case_number):
    case_details_file = f'{root_folder}/case_details.json'

    # Read the file and set all the focus nodes to false
    # Set the focus node of the case_number to true
    # Write the JSON object back to the file

    with open(case_details_file, 'r') as f:
        cases_list = json.load(f)

    for case in cases_list['cases']:
        cases_list['cases'][case]['focus'] = False
    
    cases_list['cases'][case_number]['focus'] = True

    with open(case_details_file, 'w') as f:
        json.dump(cases_list, f)


    return True






# Get the active case number
def get_active_case(root_folder):
    case_details_file = f'{root_folder}/case_details.json'

    # Read the file and get the case_number where the focus node is true
    with open(case_details_file, 'r') as f:
        cases_list = json.load(f)

    active_case = next((key for key, value in cases_list['cases'].items() if value.get('focus', False)), None)

    return active_case





# Get all the cases that this user has
def get_case_numbers(root_folder):
    case_details_file = f'{root_folder}/case_details.json'

    cases_list = []
    
    #Check if the file exists, if it does, read the JSON object from the file   
    if os.path.exists(case_details_file):
        
        #Read the file
        with open(case_details_file, 'r') as f:
            cases = json.load(f)
            #Return the case numbers which is the first node under cases
            if cases:
                cases_list = list(cases['cases'].keys())
    
    return cases_list






# Get filed in the 'documents' node
def get_files(root_folder):
    
    # Read the JSON file with the case details
    # Find a list of all the files in the files node of the case_number
    # Return the list of files

    # Get the active case number
    case_number = get_active_case(root_folder)

    with open(f'{root_folder}/case_details.json', 'r') as f:
        cases_list = json.load(f)

    files = []  # Ensure files is always a list
    if case_number in cases_list['cases']:
        case_files = cases_list['cases'][case_number].get('files')
        if case_files is not None:
            files = case_files
    return files # This is always a list which can be checked with len() on the other side






# Upload files and add embeddings to the vector store
def store_files(root_folder, files):
    # Get the active case number
    case_number = get_active_case(root_folder)

    # Create a directory to store the files if it doesn't exist
    if not os.path.exists(f'{root_folder}/{case_number}/documents'):
        os.makedirs(f'{root_folder}/{case_number}/documents')

    # Read the JSON file
    with open(f'{root_folder}/case_details.json', 'r') as f:
        cases_list = json.load(f)

    # Ensure 'files' key exists and is a list
    if 'files' not in cases_list['cases'][case_number] or cases_list['cases'][case_number]['files'] is None:
        cases_list['cases'][case_number]['files'] = []

    for each_file in files:
        # Write the file to the user/case_number/documents folder
        if hasattr(each_file, 'name'):
            this_file_path = f'{root_folder}/{case_number}/documents/{each_file.name}'
            with open(this_file_path, 'wb') as f:
                f.write(each_file.getvalue())
            
            # Add the file to the files node of the case_number if it doesn't already exist
            if each_file.name not in cases_list['cases'][case_number]['files']:
                cases_list['cases'][case_number]['files'].append(each_file.name)
    
    # Write the JSON object back to the file
    with open(f'{root_folder}/case_details.json', 'w') as f:
        json.dump(cases_list, f)

    # Update the vector store
    update_vector_store(root_folder)
    
    return True






# Delete files
def delete_files(root_folder, files):
    # Read the JSON file
    # There's a list of files to delete from the documents folder
    # Delete the files from the documents folder
    # Remove the files from the files node of the case_number
    # Update the vector store

    # Get the active case number
    case_number = get_active_case(root_folder)

    # Read the JSON file
    with open(f'{root_folder}/case_details.json', 'r') as f:
        cases_list = json.load(f)

    # Get the folder where the files are stored
    folder = f'{root_folder}/{case_number}/documents'
    
    # Delete the files from the documents folder
    for each_file in files:
        if os.path.exists(f'{folder}/{each_file}'):
            os.remove(f'{folder}/{each_file}')
            
            # If the file name exists in the 'file' node, remove the file from the files node of the case_number
            if each_file in cases_list['cases'][case_number]['files']:
                cases_list['cases'][case_number]['files'].remove(each_file)
    
    # Write the JSON object back to the file
    with open(f'{root_folder}/case_details.json', 'w') as f:
        json.dump(cases_list, f)

    
    # Update the vector store
    update_vector_store(root_folder)
    
    return True






def update_vector_store(root_folder):
    
    # Get the documents from the 'documents' node
    # Read the documents
    # Split the documents into chunks
    # Create the chunk IDs
    # Check which chunks are already in the vector store
    # Add the new chunks to the vector store

    # Get the active case number
    case_number = get_active_case(root_folder)
    files_folder = f'{root_folder}/{case_number}/documents'
    vectors_folder = f'{root_folder}/{case_number}/vectors'

    # Get the list of files from the JSON object
    with open(f'{root_folder}/case_details.json', 'r') as f:
        cases_list = json.load(f)
    
    files = cases_list['cases'][case_number]['files']

    if files != 'null':
        if len(files) > 0:
            # Load each of the documents and add it to the document_loader
            documents = []
            for each_file in files:
                if each_file.endswith('.pdf'):

                    # Load the PDF file
                    document_loader = PyPDFium2Loader(f'{files_folder}/{each_file}')
                    doc = document_loader.load()
                    content = doc[0].page_content

                    if len(content) < 3:
                        #Try loading the file with PyPDF
                        document_loader = PyPDFLoader(f'{files_folder}/{each_file}')
                        doc = document_loader.load()
                        content = doc[0].page_content
                    
                    #Add it to the documents object
                    documents.extend(doc)

            # Check if the vector store folder exists, otherwise create it
            if not os.path.exists(vectors_folder):
                print(f"👉 Vector store folder doesn't exist. Creating it...")
                os.makedirs(vectors_folder)

            # Load the existing database
            try:
                db = Chroma(
                    persist_directory=vectors_folder, embedding_function=embeddings
                )
            except ValueError as e:
                print(f"👉 Error initializing vector store: {e}")
                return
            
            chunks = split_documents(documents)
            chunks_with_ids = calculate_chunk_ids(chunks)
            
            # Debugging
            print(f"👉 Length of chunks: {len(chunks_with_ids)}")

            # Add or Update the documents.
            existing_items = db.get(include=[])  # IDs are always included by default
            existing_ids = set(existing_items["ids"])
            print(f"Existing documents in DB: {len(existing_ids)}")

            # Only add documents that don't exist in the DB.
            new_chunks = []
            for chunk in chunks_with_ids:
                if chunk.metadata["id"] not in existing_ids:
                    new_chunks.append(chunk)

            if len(new_chunks):
                print(f"👉 New chunks added: {len(new_chunks)}")
                new_chunk_ids = [chunk.metadata["id"] for chunk in new_chunks]
                db.add_documents(new_chunks, ids=new_chunk_ids)

            # Remove documents in existing_ids that are not in chunks_with_ids
            # THIS FUNCTION SHOULD EVENTUALLY BE IN THE FILE MANAGEMENT MODULE
            remove_chunk_ids = list(existing_ids - set(chunk.metadata["id"] for chunk in chunks_with_ids))
            if len(remove_chunk_ids):
                db.delete(ids=remove_chunk_ids)
                print(f"✅ Removed chunks: {len(remove_chunk_ids)}")

            return db
        
        else:
            print("👉 Node exists but no case files")
    else:
        print("👉 First run, no files in case")

    return False






def split_documents(documents: list[Document]):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100,
        length_function=len,
        is_separator_regex=False,
    )
    return text_splitter.split_documents(documents)






def calculate_chunk_ids(chunks):

    # This will create IDs like "data/monopoly.pdf:6:2"
    # Page Source : Page Number : Chunk Index

    last_page_id = None
    current_chunk_index = 0

    for chunk in chunks:
        source = chunk.metadata.get("source")
        page = chunk.metadata.get("page")
        current_page_id = f"{source}:{page}"

        # If the page ID is the same as the last one, increment the index.
        if current_page_id == last_page_id:
            current_chunk_index += 1
        else:
            current_chunk_index = 0

        # Calculate the chunk ID.
        chunk_id = f"{current_page_id}:{current_chunk_index}"
        last_page_id = current_page_id

        # Add it to the page meta-data.
        chunk.metadata["id"] = chunk_id

    return chunks





TIMELINE_SYSTEM_PROMPT_TEMPLATE = """
As a highly competent legal advisor, you recognize the critical importance of accurately detailing the timeline of events for a case. You are tasked with assisting the user by providing a detailed and precise timeline of events related to the case. Each entry in the timeline must include the date of the event and a brief description of what happened on that date.

Key criteria for your response:

1. Date Format: Ensure dates are in the 'dd mmm yyyy' format (e.g., '25 Jan 2023').
2. Chronological Order: Events must be strictly in chronological order.
3. JSON Format: Return the information as a JSON object named 'timeline' with 'date' and 'event' as the key-value pairs. Ensure all quotes are properly escaped.
4. Double-Checking: Verify the timeline for any errors and remove duplicated events before submission.

Here is the format you should follow:

{{
    "timeline": [
        {{
            "date": "date_1",
            "event": "event_1"
        }},
        {{
            "date": "date_2",
            "event": "event_2"
        }}
        // Add more entries as needed
    ]
}}


Or, if there are no other events to include outside of those specified in the list above, return an empty JSON object like this:

{{
    "timeline": []
}}

Remember, respond only with the valid JSON object.
"""

TIMELINE_PROMPT_TEMPLATE = """
For context, the following are some of the events that took place as per the documents provided:

---
{context}
---

Now, compile all the identified dates and corresponding events, excluding those from the list below:

---
{exclude_events}
---

Ensure your response includes only the valid JSON object and absolutely nothing else.
"""

def get_timeline(root_folder, refresh=False):

    # Read the case_details JSON file
    # See if the timeline node exists
    # If it doesn't exist, create it
    # If it exists, get the timeline
    # If refresh is true, generate a new timeline

    # Get the active case number
    case_number = get_active_case(root_folder)
    vectors_folder = f'{root_folder}/{case_number}/vectors'

    # Prepare the DB.
    db = Chroma(persist_directory=vectors_folder, embedding_function=embeddings)

    # Read the JSON file
    with open(f'{root_folder}/case_details.json', 'r') as f:
        cases_list = json.load(f)
    
    # Read the timeline node from the specific case
    timeline_data = cases_list['cases'][case_number].get('timeline', [])
    existing_dates = timeline_data if timeline_data is not None else []

    # Check if the timeline length is zero, if it is, set refresh to True
    if len(existing_dates) == 0:
        refresh = True

    if refresh:
        results = db.similarity_search_with_score("Find the most recent dates of any events mentioned in the documents that are pertinent to this current case.", k=50)
        context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in results])
        
        system_template = ChatPromptTemplate.from_template(TIMELINE_SYSTEM_PROMPT_TEMPLATE)
        system_prompt = system_template.format()
        prompt_template = ChatPromptTemplate.from_template(TIMELINE_PROMPT_TEMPLATE)
        # Format existing_dates as text with each line as "date: event"
        if existing_dates != 'null':
            exclusion_dates = "\n".join([f"{item['date']}: {item['event']}" for item in existing_dates])
        else:
            exclusion_dates = "No events or dates were previously found."
        prompt = prompt_template.format(context=context_text, exclude_events=exclusion_dates)
        print(f"👉 Timeline Prompt: {prompt}")

        system_message = SystemMessage(content=system_prompt)
        user_message = HumanMessage(content=prompt)

        response = llm_eco([system_message, user_message], response_format={"type": "json_object"})
        
        if isinstance(response, AIMessage):
            response = response.content.strip()

        try:
            timeline = json.loads(response)
        except json.JSONDecodeError:
            print(f"Error: Cannot parse JSON: {response}")
            # Set the timeline to an empty JSON object
            timeline = {}
            
        # Add to the existing dates
        if isinstance(existing_dates, list):
            existing_dates += timeline.get('timeline', [])
        else:
            existing_dates = timeline.get('timeline', [])
        
        print(f"👉 Additional Dates: {timeline.get('timeline', [])}")

        # Sort the timeline by date
        existing_dates = sorted(existing_dates, key=lambda x: parse_date(x['date']))

        # Write the updated dates to the file
        cases_list['cases'][case_number]['timeline'] = existing_dates
        with open(f'{root_folder}/case_details.json', 'w') as f:
            json.dump(cases_list, f)

    # Initialize an empty string for the markdown content
    markdown_string = ""

    # Directly iterate through the list of events in existing_dates
    print(f"👉 Existing Dates: {existing_dates}")
    if existing_dates != 'null':
        for item in reversed(existing_dates):
            # Format each item as markdown and append it to the markdown_string
            # If a date is in the future, display that in red
            # If it's the last item, don't add the horizontal rule

            if parse_date(item['date']) > datetime.now():
                markdown_string += f"🚨 **{item['date']}**:\n\n{item['event']}\n\n"
            else:
                markdown_string += f"**{item['date']}:**\n\n{item['event']}\n\n"
            
            if item != existing_dates[0]:
                markdown_string += "---\n\n"
    else:
        markdown_string = "No events found in the documents. Try hitting the refresh button if you've uploaded new documents that need to be processed."

    # markdown_string now contains the entire content in markdown format

    return markdown_string






def parse_date(date_string):
    try:
        return datetime.strptime(date_string, "%d.%m.%Y")
    except ValueError:
        try:
            return parse(date_string)
        except ValueError:
            print(f"Error: Cannot parse date: {date_string}")
            return None






def delete_timeline(root_folder):
    # Read the case_details JSON file
    # Get the active case number
    # See if the timeline node exists for the active case
    # If it exists, delete it
    # Write the JSON object back to the file

    # Get the active case number
    case_number = get_active_case(root_folder)

    # Read the JSON file
    with open(f'{root_folder}/case_details.json', 'r') as f:
        cases_list = json.load(f)

    # Delete the timeline node from the specific case
    cases_list['cases'][case_number]['timeline'] = 'null'

    # Write the JSON object back to the file
    with open(f'{root_folder}/case_details.json', 'w') as f:
        json.dump(cases_list, f)
    
    return True





ACTORS_SYSTEM_PROMPT_TEMPLATE = """As a highly competent legal advisor, you know the importance of correctly identifying all main people and entities involved in a legal case. Your task is to assist the user by providing a detailed and organized list of all names of persons and entities associated with this case, along with their respective roles.

Your approach should include:

1. Reviewing the existing list of names and roles provided.
2. Identifying additional names of defendants, plaintiffs, and other significant individuals or entities not already mentioned.
3. Grouping names appropriately (e.g., by role such as defendants, plaintiffs, witnesses, etc.).
4. Ensuring no duplicates within each group and that each name appears only once.
5. Correcting or removing any inaccuracies from the provided list if necessary.

Your response should be formatted in Markdown. Use a list format to present the individuals and entities clearly.
"""

ACTORS_PROMPT_TEMPLATE = """
Here are the names already identified in the documents for your reference:

---
{context}
---

Now, find and add the names of any additional defendants, plaintiffs, and other significant individuals involved in this case that are not listed above. Ensure there are no duplicates and the list is accurate. If no new names need to be added, you can simply respond with the current list. If any names need to be removed, make the necessary corrections and provide the updated list.
"""

def get_actors(root_folder, refresh=False):
    
    # Get the active case number
    case_number = get_active_case(root_folder)

    # Read the case_details JSON file
    with open(f'{root_folder}/case_details.json', 'r') as f:
        cases_list = json.load(f)
        
    # See if the actors node exists for the active case
    actors = cases_list['cases'][case_number].get('actors', 'null')
    
    # If it doesn't exist or 'refresh' is true, generate a new actors list and write it back to the file
    if refresh or actors == 'null':
        # Prepare the DB.
        vectors_folder = f'{root_folder}/{case_number}/vectors'
        db = Chroma(persist_directory=vectors_folder, embedding_function=embeddings)

        results = db.similarity_search_with_score("Who are the defendants, plaintiffs, other significant individuals and entities involved in this case?", k=20)
        context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in results])

        system_template = PromptTemplate.from_template(ACTORS_SYSTEM_PROMPT_TEMPLATE)
        user_template = PromptTemplate.from_template(ACTORS_PROMPT_TEMPLATE)
        system_prompt = system_template.format()
        user_prompt = user_template.format(context=context_text)

        system_message = SystemMessage(content=system_prompt)
        user_message = HumanMessage(content=user_prompt)

        # Use the correct method to call the LLM
        response = llm_eco([system_message, user_message])

        # The response from llm should be an AIMessage object
        if isinstance(response, AIMessage):
            print(f"✅ Response: {response}")
            actors = response.content.strip()
        else:
            raise Exception(f"Unexpected response type: {type(response)}")

        # Write it to the file
        cases_list['cases'][case_number]['actors'] = actors
        with open(f'{root_folder}/case_details.json', 'w') as f:
            json.dump(cases_list, f)

    return actors






def delete_actors(root_folder):
    # Read the case_details JSON file
    # Get the active case number
    # See if the actors node exists for the active case
    # If it exists, delete it
    # Write the JSON object back to the file

    # Get the active case number
    case_number = get_active_case(root_folder)

    # Read the JSON file
    with open(f'{root_folder}/case_details.json', 'r') as f:
        cases_list = json.load(f)

    # Delete the actors node from the specific case
    cases_list['cases'][case_number]['actors'] = 'null'

    # Write the JSON object back to the file
    with open(f'{root_folder}/case_details.json', 'w') as f:
        json.dump(cases_list, f)
    
    return True





QUERY_SYSTEM_PROMPT_TEMPLATE = """As a highly competent legal advisor with extensive knowledge of Indian law, your task is to assist the user by answering questions related to a specific legal suit. You will act as part of {party}'s legal team, who is the {side} in this case. Your role involves not only answering the immediate question asked by the user but also performing thorough research into relevant laws and precedents that pertain to the question.

Your approach should be systematic:

1. Clearly understand the user's question.
2. Break down the question into necessary components.
3. Conduct research to identify relevant legal statutes, case laws, or principles.
4. Provide a direct and concise response to the user's question.

Use Markdown to format your response effectively:

- Organize different sections (e.g., Direct Answer and Additional Details) of the answer using bold fonts and uppercase letters.
- Apply bullet points or numbered lists for clarity.
- Use italics and bold formatting for key terms and for emphasis."""

QUERY_PROMPT_TEMPLATE="""The user's current question is as follows:
---
{question}
---

The following excerpts from the case documents are relevant to the user's question:
---
{context}
---

Now, based on the above information, answer the user's question."""

def get_response(vectors_folder, user_query, which_side, party_names):
    # Function to perform RAG (Retrieval-Augmented Generation)
    
    # Load the vector store
    db = Chroma(persist_directory=vectors_folder, embedding_function=embeddings)

    # 2. Search for the relevant documents
    results = db.similarity_search_with_score(user_query, k=25)
    context_text = "\n\n".join([doc.page_content for doc, _score in results])

    # Formulate the full query prompt with the retrieved context
    prompt_template = ChatPromptTemplate.from_template(QUERY_PROMPT_TEMPLATE)
    full_prompt = prompt_template.format(
        # chat_history=chat_history.messages,  #Getting rate limit errors, so disabling chat history for now
        question=user_query,
        context=context_text
    )

    # Include the system prompt detailing the role (QUERY_SYSTEM_PROMPT_TEMPLATE)
    system_template = QUERY_SYSTEM_PROMPT_TEMPLATE.format(
        party=party_names,
        side=which_side
    )

    # Format the user and system messages as objects
    system_message = SystemMessage(content=system_template)
    user_message = HumanMessage(content=full_prompt)

    # Use the correct method to call the LLM
    response = llm([system_message, user_message])

    # The response from llm should be an AIMessage object
    if isinstance(response, AIMessage):
        return response
    else:
        raise Exception(f"Unexpected response type: {type(response)}")






CASE_LAWS_SYSTEM_PROMPT_TEMPLATE = """As a highly competent legal advisor with extensive knowledge of Indian law, your role is to assist the user by answering questions related to a legal suit. You will act as part of {party}'s legal team, who is the {side} in this case. You understand that legal precedents are pivotal not only for predicting the likely outcome of the case but also for devising the most effective strategy to win arguments.

Your task involves:

1. Identifying cases similar to the one at hand, based on the underlying matter, relevant sections of law, or other comparable legal principles.
2. Listing the names of these cases.
3. Providing a brief sentence for each case that explains its similarity to the current case.

Ensure your response is well-organized and formatted using Markdown:

- Organize different sections (e.g., Direct Answer and Additional Details) of the answer using bold fonts and uppercase letters.
- Include case names and brief descriptions clearly and concisely.
"""

CASE_LAWS_PROMPT_TEMPLATE = """Here is the context of your conversation with the user so far for reference:
--- 
{chat_history}
---
Now, identify and list the cases relevant to the last point being discussed in this conversation."""

def get_case_laws(which_side, party_names, messages, index):
    # Function to look up case laws based on the last point discussed in the conversation

    # Start iterating backwards from the index position and find the user's last question
    for i in range(index, -1, -1):
        if isinstance(messages[i], HumanMessage):
            start_index = i
            break
    
    # Build the chat history from the start_index to the index
    chat_history = "\n\n".join([msg.content for msg in messages[start_index:index+1]])
    

    # Formulate the case law query prompt
    system_template = PromptTemplate.from_template(CASE_LAWS_SYSTEM_PROMPT_TEMPLATE)
    user_template = PromptTemplate.from_template(CASE_LAWS_PROMPT_TEMPLATE)
    
    system_prompt = system_template.format(party=party_names, side=which_side)
    user_prompt = user_template.format(chat_history=chat_history)

    print(f"✅ Case Law Prompts: {system_prompt} \n\n {user_prompt}")

    system_message = SystemMessage(content=system_prompt)
    user_message = HumanMessage(content=user_prompt)

    # Use the correct method to call the LLM
    response = llm([system_message, user_message])

    # The response from llm should be an AIMessage object
    if isinstance(response, AIMessage):
        return response
    else:
        raise Exception(f"Unexpected response type: {type(response)}")





OPPOSITIONS_ARGUMENTS_SYSTEM_PROMPT_TEMPLATE = """As a highly competent legal advisor with extensive knowledge of Indian law, your role is to assist the user (who is {party} and the {side} in this case), by simulating the perspective of the opposition's legal team. This involves crafting potential counterarguments against the latest point discussed in the conversation. By understanding the arguments that the opposition could make, you strengthen the user's preparation and strategy for the case.

Your approach should involve:

1. Reviewing the latest point discussed.
2. Researching similar and relevant cases to identify possible counterarguments.
3. Listing the headings of these counterarguments.
4. Providing a brief but clear description of each argument to ensure the user easily understands the opposition's potential stance.

Ensure your response is structured and formatted effectively using Markdown:

- Organize different sections (e.g., Direct Answer and Additional Details) of the answer using bold fonts and uppercase letters.
- Include brief descriptions under each header.
- Keep your explanations concise and focused on clarity."""

OPPOSITIONS_ARGUMENTS_PROMPT_TEMPLATE = """
For your reference, here is the conversation with the user so far:
---
{chat_history}
---
Now, proceed with the research and present the potential counterarguments from the opposition's perspective."""

def get_opposition_arguments(which_side, party_names, messages, index):
    # Function the generate potential counterarguments from the opposition's perspective

     # Start iterating backwards from the index position and find the user's last question
    for i in range(index, -1, -1):
        if isinstance(messages[i], HumanMessage):
            start_index = i
            break
    
    # Build the chat history from the start_index to the index
    chat_history = "\n\n".join([msg.content for msg in messages[start_index:index+1]])

    # Formulate the case law query prompt
    system_template = PromptTemplate.from_template(OPPOSITIONS_ARGUMENTS_SYSTEM_PROMPT_TEMPLATE)
    user_template = PromptTemplate.from_template(OPPOSITIONS_ARGUMENTS_PROMPT_TEMPLATE)
    
    system_prompt = system_template.format(party=party_names, side=which_side)
    user_prompt = user_template.format(chat_history=chat_history)

    print(f"✅ Opposition Research Prompt: {user_prompt}")

    system_message = SystemMessage(content=system_prompt)
    user_message = HumanMessage(content=user_prompt)

    # Use the correct method to call the LLM
    response = llm([system_message, user_message])

    # The response from llm should be an AIMessage object
    if isinstance(response, AIMessage):
        return response
    else:
        raise Exception(f"Unexpected response type: {type(response)}")




DOCUMENT_REFERENNCES_PROMPT_TEMPLATE = """As a legal advisor with a keen eye for detail, your role is to assist the user develop a list of references which were relevant to the user's last query. Go through the document excepts and identify the most pertinent references that could be useful in answering the user's last query.

Your approach should be:

1. Reviewing the user's last query.
2. Scanning the document excerpts to find relevant references.
3. Listing the exact file name and extension of the document, page numbers and a brief excerpt of the content that is up to 200 characters long.
4. Formatting the response in a clear and organized manner using Markdown.

The user's last query was:
___
{user_query}
___

The relevant document excerpts are:
___
{document_excerpts}
___

Now, compile the list of document references that could be useful to the user.
"""

def get_document_references(vectors_folder, messages, index):
    #Function to get the document references from the list of files we have in the case

    # Find the last user message before the current index
    for j in range(index, -1, -1):
        if isinstance(messages[j], HumanMessage):
            user_query = messages[j].content
            break
    
    # Load the vector store
    db = Chroma(persist_directory=vectors_folder, embedding_function=embeddings)

    # Search for the relevant documents
    results = db.similarity_search_with_score(user_query, k=10)

    # Iterate through the results and create a list of document references with the file numbers, page numbers, and excerpts
    document_excerpts = ""
    for doc, score in results:
        file_name = os.path.basename(doc.metadata.get("source"))
        page_number = doc.metadata.get("page")
        excerpt = doc.page_content[:200]
        document_excerpts += f"\n\n---\n\n File Name: {file_name} \n Page Number: {page_number}) \n Excerpt:{excerpt}...\n\n---\n\n"
    
    # Format the prompts
    user_template = ChatPromptTemplate.from_template(DOCUMENT_REFERENNCES_PROMPT_TEMPLATE)
    user_prompt = user_template.format(user_query=user_query, document_excerpts=document_excerpts) 

    # Ask the llm model to generate the response
    user_message = HumanMessage(content=user_prompt)
    response = llm_eco([user_message])

    if isinstance(response, AIMessage):
        return response
    else:
        raise Exception(f"Unexpected response type: {type(response)}")




def get_additional_context(message):
    # Function that will find additional details of the legal point provided as an answer to the user's previous question

    return True