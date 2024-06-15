       
# Standard Python libraries
import os
import fnmatch
import json
import yaml
import pandas as pd
import streamlit as st
import streamlit_authenticator as stauth

from yaml.loader import SafeLoader
from datetime import datetime
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_community.document_loaders import PyPDFDirectoryLoader
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

QUERY_SYSTEM_PROMPT_TEMPLATE = """As a highly competent legal advisor with extensive knowledge of Indian law, your task is to assist the user by answering questions related to a specific legal suit. You will act as part of {party}'s legal team, who is the {side} in this case. Your role involves not only answering the immediate question asked by the user but also performing thorough research into relevant laws and precedents that pertain to the question.

Your approach should be systematic:

1. Clearly understand the user's question.
2. Break down the question into necessary components.
3. Conduct research to identify relevant legal statutes, case laws, or principles.
4. Provide a direct and concise response to the user's question.
5. Follow up with additional context or detailed explanations as necessary.
5. If there are any unsubstantiated points made by the opposing side, mention them briefly to highlight weaknesses in their arguments.

Use Markdown to format your response effectively:

- Utilize headers (e.g., ##, ###) to organize different sections (e.g., Direct Answer, Legal Context, Additional Insights, Opposing Side's Weak Points).
- Apply bullet points or numbered lists for clarity.
- Italicize or bold key terms for emphasis."""

QUERY_PROMPT_TEMPLATE="""Here is the context of your conversation with the user so far for reference:
---
{chat_history}
---

The user's current question is as follows:
---
{question}
---

The following excerpts from the case documents are relevant to the user's question:
---
{context}
---

Now, based on the above information, answer the user's question comprehensively."""

OPPOSITIONS_ARGUMENTS_SYSTEM_PROMPT_TEMPLATE = """As a highly competent legal advisor with extensive knowledge of Indian law, your role is to assist the user (who is {party} and the {side} in this case), by simulating the perspective of the opposition's legal team. This involves crafting potential counterarguments against the latest point discussed in the conversation. By understanding the arguments that the opposition could make, you strengthen the user's preparation and strategy for the case.

Your approach should involve:

1. Reviewing the latest point discussed.
2. Researching similar and relevant cases to identify possible counterarguments.
3. Listing the headings of these counterarguments.
4. Providing a brief but clear description of each argument to ensure the user easily understands the opposition’s potential stance.

Ensure your response is structured and formatted effectively using Markdown:

- Use headers (e.g., ##, ###) for each counterargument to separate them.
- Include brief descriptions under each header.
- Keep your explanations concise and focused on clarity."""

OPPOSITIONS_ARGUMENTS_PROMPT_TEMPLATE = """
For your reference, here is the conversation with the user so far:
---
{chat_history}
---
Now, proceed with the research and present the potential counterarguments from the opposition's perspective."""


CASE_LAWS_SYSTEM_PROMPT_TEMPLATE = """As a highly competent legal advisor with extensive knowledge of Indian law, your role is to assist the user by answering questions related to a legal suit. You will act as part of {party}'s legal team, who is the {side} in this case. You understand that legal precedents are pivotal not only for predicting the likely outcome of the case but also for devising the most effective strategy to win arguments.

Your task involves:

1. Identifying cases similar to the one at hand, based on the underlying matter, relevant sections of law, or other comparable legal principles.
2. Listing the names of these cases.
3. Providing a brief sentence for each case that explains its similarity to the current case.

Ensure your response is well-organized and formatted using Markdown:

- Use headers (e.g., ##, ###) to separate the various cases.
- Include case names and brief descriptions clearly and concisely.
"""

CASE_LAWS_PROMPT_TEMPLATE = """Here is the context of your conversation with the user so far for reference:
--- 
{chat_history}
---
Now, identify and list the cases relevant to the last point being discussed in this conversation."""



TIMELINE_SYSTEM_PROMPT_TEMPLATE = """
As a highly competent legal advisor, you recognize the critical importance of accurately detailing the timeline of events for a case. You are tasked with assisting the user by providing a detailed and precise timeline of events related to the case. Each entry in the timeline must include the date of the event and a brief description of what happened on that date.

Key criteria for your response:

1. Date Format: Ensure dates are in the 'dd mmm yyyy' format (e.g., '25 Jan 2023').
2. Chronological Order: Events must be strictly in chronological order.
3. JSON Format: Return the information as a JSON object named 'timeline' with 'date' and 'event' as the key-value pairs. Ensure all quotes are properly escaped.
4. Double-Checking: Verify the timeline for any errors before submission.

Here is the format you should follow:

{
  "timeline": [
    {
      "date": "date_1",
      "event": "event_1"
    },
    {
      "date": "date_2",
      "event": "event_2"
    }
    // Add more entries as needed
  ]
}


Or, if there are no more events:

{
  "timeline": []
}

Remember, respond only with the valid JSON object.
"""

TIMELINE_PROMPT_TEMPLATE = """
For context, the following are the events that took place:

---
{context}
---

Now, compile all the identified dates and corresponding events, excluding those from the list below:

---
{exclude_events}
---

If there are no additional events to include outside of those specified in the list above, return an empty JSON object. Ensure your response includes only the valid JSON object and absolutely nothing else. 
"""


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


# QUERY_PROMPT_TEMPLATE="""
# For your reference, your conversation with the user so far is as follows:

# {chat_history}
# ____

# The user's current question below:

# {question}

# ____

# The following excerpts from the documents of the case are relevant to the question asked by the user:

# {context}

# Now, answer the user's question.
# """

# OPPOSITIONS_ARGUMENTS_SYSTEM_PROMPT_TEMPLATE="""
# As a highly competent legal advisor with extensive knowledge of the Indian law, you assist the user by answering questions related to a legal suit. You will act as a part of {party}'s legal team who is the {side} in this case. You understand that for a case to be strong, it is important to understand the arguments that the opposition could make. You will therefore pretend to be the opposition's legal team and find arguments that could be made against the last point discussed in the conversation. You do this by finding what happened in other cases that are similar and relevant to the point being discussed in the case at hand. 

# You will only list the heading of the argument and a brief description of the argument to make it simple for the user to understand. You should use markdown to format your response, using headers to separate the various arguments.""" 

# OPPOSITIONS_ARGUMENTS_PROMPT_TEMPLATE="""
# For your reference, your conversation with the user so far is as follows:

# {chat_history}
# ____

# Now, do the research from the opposition's perspective.
# """

# CASE_LAWS_SYSTEM_PROMPT_TEMPLATE="""
# As a highly competent legal advisor with extensive knowledge of the Indian law, you assist the user by answering questions related to a legal suit. You will act as a part of {party}'s legal team who is the {side} in this case. You understand that precedents are very important to not only understand the likely outcome of the case at hand, but also the right strategy that should be used to win arguments. So you will find cases that are similar to the case at hand based on the underlying matter, sections of law or cases that lawyers find similar in other ways. You will only list the names of cases and a brief sentence about it's similarity.

# You should use markdown to format your response, using headers to separate the various cases you find.""" 

# CASE_LAWS_PROMPT_TEMPLATE="""
# For your reference, your conversation with the user so far is as follows:

# {chat_history}
# ____

# Now, find the cases relevant to the last point being discussed in this conversation.
# """

# TIMELINE_SYSTEM_PROMPT_TEMPLATE = """
# As a highly competent legal advisor, you understand how important it is to get the timeline of events correct. You assist the user by providing a detailed timeline of events related to the case. You will always return the date of an event and a short event description of what happened on that date. The dates are very likely to be in the 'dd.mm.yyyy' format. You must be careful and provide the timeline only in a chronological order and you will therefore double-check your response before sending it. Send the information as a JSON object called 'timeline' and with 'date' and 'event' as the two key-value pairs. Make sure all the quotes are escaped properly. The dates must be formatted in the 'dd mmm yyyy' format when possible. Always respond only with the valid JSON object, and absolutely nothing else.
# """

# TIMELINE_PROMPT_TEMPLATE = """
# For context, the following are the events that took place:

# {context}

# Now, find all the dates and events mentioned in the documents that are not below:

# {exclude_events}

# If there are no more events to add, you can respond with an empty JSON object. But remember to only respond with a valid JSON object.
# """

# ACTORS_SYSTEM_PROMPT_TEMPLATE = """
# As a highly competent legal advisor, you understand how important it is to get the names of all the main people and entities in the case correct. You assist the user by providing a detailed list of all the names of people and entities along with their roles in this case. Wherever grouping of these names is required, please do so and format your response as markdown and the individuals and entities should be in a list format. 
# """

# ACTORS_PROMPT_TEMPLATE = """
# The following names have already been identified in the documents:

# {context}

# Now, find all the names of the defendants, plaintiffs and other significant individuals involved in this case that are not already mentioned in the above list. Make sure that there are no duplicates in your response and see that a name appears only once within a group. If no names are required to be added to the list above, you can simply respond with the same list. If you need to remove any names from the list above, please do so and then respond with the updated list.
# """




# For main operations
llm = ChatOpenAI(openai_api_key=OPENAI_API_KEY, model_name="gpt-4o", temperature=0.3)
llm_eco = ChatOpenAI(openai_api_key=OPENAI_API_KEY, model_name="gpt-4o", temperature=0.3) #Change this to something else in the future, but for now gpt-3.5-turbo is not providing the best answers
embeddings = OpenAIEmbeddings(model=EMBEDDINGS_MODEL, api_key=OPENAI_API_KEY)
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
    
    





#Write the case details to a file
def put_case_details(root_folder, case_number, which_side, party_names):
    case_details_file = f'{root_folder}/case_details.txt'

    with open(case_details_file, 'w') as f:
        f.write(f'Case Number: {case_number}\n')
        f.write(f'Side: {which_side}\n')
        f.write(f'Party Names: {party_names}\n')






#Read the case details from a file if it exists
def get_case_details(root_folder):
    case_details_file = f'{root_folder}/case_details.txt'
    
    if os.path.exists(case_details_file):
        with open(case_details_file, 'r') as f:
            lines = f.readlines()
            case_number = lines[0].split(": ")[1].strip()
            which_side = lines[1].split(": ")[1].strip()
            party_names = lines[2].split(": ")[1].strip()
            return case_number, which_side, party_names
    else:
        return "", "", ""






# Display files in the sidebar
def get_files_in_folder(folder):

    if os.path.exists(folder):
        # Get a list of all files in the 'casefiles' directory and display it in the sidebar
        files = [f for f in os.listdir(folder) if fnmatch.fnmatch(f, '*.pdf') or fnmatch.fnmatch(f, '*.txt')]
        print(f"👉 Files in {folder}: {files}")
        return files
    else:
        return []






# Upload files and add embeddings to the vector store
def store_files(folder, files):

    # Create a directory to store the files if it doesn't exist
    if not os.path.exists(folder):
        os.makedirs(folder)

    for each_file in files:
        # Write the file to the 'casefiles' directory
        if hasattr(each_file, 'name'):
            this_file_path = f'{folder}/{each_file.name}'
            with open(this_file_path, 'wb') as f:
                f.write(each_file.getvalue())

    # Read all the files and add/update the vector store with them
    document_loader = PyPDFDirectoryLoader(folder)
    documents = document_loader.load()
    print(f"👉 Number of documents: {len(documents)}")
    
    vectors_folder = f'{os.path.dirname(folder)}/vectors'
    update_vector_store(vectors_folder, documents)
    
    return vector_store






def update_vector_store(vectors_folder, documents: list[Document]):
    # Split the documents into chunks
    # Create the chunk IDs
    # Check which chunks are already in the vector store
    # Add the new chunks to the vector store

    # Check if the vector store folder exists, otherwise create it
    if not os.path.exists(vectors_folder):
        print(f"👉 Vector store folder doesn't exist. Creating it...")
        os.makedirs(vectors_folder)


    # Load the existing database.
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
        print(f"👉 New documents added: {len(new_chunks)}")
        new_chunk_ids = [chunk.metadata["id"] for chunk in new_chunks]
        db.add_documents(new_chunks, ids=new_chunk_ids)

    # Remove documents in existing_ids that are not in chunks_with_ids
    # THIS FUNCTION SHOULD EVENTUALLY BE IN THE FILE MANAGEMENT MODULE
    remove_chunk_ids = list(existing_ids - set(chunk.metadata["id"] for chunk in chunks_with_ids))
    if len(remove_chunk_ids):
        db.delete(ids=remove_chunk_ids)
        print(f"✅ Removed documents: {len(remove_chunk_ids)}")

    return db






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





def get_timeline(vectors_folder, timeline_file, refresh=False):

    # Prepare the DB.
    db = Chroma(persist_directory=vectors_folder, embedding_function=embeddings)

    # Check if the timeline file exists
    if not os.path.exists(timeline_file):
        with open(timeline_file, 'w') as f:
            f.write('{"timeline": []}')
        refresh = True # Set this flag to true in case of a first run so that a new timeline is generated

    if refresh:
        results = db.similarity_search_with_score("Find all the dates of any events mentioned in the documents that are pertinent to this current case.", k=25)
        context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in results])
        
        system_template = ChatPromptTemplate.from_template(TIMELINE_SYSTEM_PROMPT_TEMPLATE)
        system_prompt = system_template.format()
        prompt_template = ChatPromptTemplate.from_template(TIMELINE_PROMPT_TEMPLATE)
        prompt = prompt_template.format(context=context_text, exclude_events=existing_dates)

        system_message = SystemMessage(content=system_prompt)
        user_message = HumanMessage(content=prompt)

        response = llm_eco([system_message, user_message], response_format={"type": "json_object"})
        
        if isinstance(response, AIMessage):
            response = response.content.strip()

        # # Parse the response
        # response = response[response.find('{'):response.rfind('}')+1]
        # print(f"✅ Parsed Response: {response}")
        try:
            timeline = json.loads(response)
        except json.JSONDecodeError:
            print(f"Error: Cannot parse JSON: {response}")
            timeline = {}
            

        # Update existing dates
        existing_dates.update(timeline)

        # Write the updated dates to the file
        with open(timeline_file, 'w') as f:
            json.dump(existing_dates, f)

    # Get existing dates from the file
    with open(timeline_file, 'r') as f:
        existing_dates = json.load(f)

    # Sort the timeline by date
    timeline_sorted = sorted(existing_dates['timeline'], key=lambda x: parse_date(x['date']))


    # Create the markdown string
    timeline_markdown = "\n".join(f"\n**{item['date']}**:\n\n {item['event']}" for item in timeline_sorted)

    return timeline_markdown






def parse_date(date_string):
    try:
        return datetime.strptime(date_string, "%d.%m.%Y")
    except ValueError:
        try:
            return parse(date_string)
        except ValueError:
            print(f"Error: Cannot parse date: {date_string}")
            return None








def get_actors(vectors_folder, actors_file, refresh=False):
    # Prepare the DB.
    db = Chroma(persist_directory=vectors_folder, embedding_function=embeddings)

    # Check if the actors file exists
    if not os.path.exists(actors_file):
        with open(actors_file, 'w') as f:
            f.write('')

    # Get existing actors
    with open(actors_file, 'r') as f:
        response = f.read()


    if refresh or response == '':
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
            response_content = response.content.strip()
        else:
            raise Exception(f"Unexpected response type: {type(response)}")

        # Write it to the file
        with open(actors_file, 'w') as f:
            f.write(response_content)

        return response_content
    else:
        return response






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
        chat_history=chat_history.messages,
        question=user_query,
        context=context_text
    )

    # Include the system prompt detailing the role (QUERY_SYSTEM_PROMPT_TEMPLATE)
    system_template = QUERY_SYSTEM_PROMPT_TEMPLATE.format(
        party=party_names,
        side=which_side
    )

    # Generate the response using the LLM
    system_message = SystemMessage(content=system_template)
    user_message = HumanMessage(content=full_prompt)

    # Add the system and user messages to the chat history
    chat_history.add_message(system_message)
    chat_history.add_message(user_message)

    # Use the correct method to call the LLM
    response = llm([system_message, user_message])

    # The response from llm should be an AIMessage object
    if isinstance(response, AIMessage):
        response_content = response.content.strip()
    else:
        raise Exception(f"Unexpected response type: {type(response)}")

    # Add the AI's response to the chat history
    chat_history.add_message(AIMessage(content=response_content))
    

    return AIMessage(content=response_content)







def get_case_laws(which_side, party_names):
    # Function to look up case laws based on the last point discussed in the conversation

    # Formulate the case law query prompt
    system_template = PromptTemplate.from_template(CASE_LAWS_SYSTEM_PROMPT_TEMPLATE)
    user_template = PromptTemplate.from_template(CASE_LAWS_PROMPT_TEMPLATE)
    
    system_prompt = system_template.format(party=party_names, side=which_side)
    user_prompt = user_template.format(chat_history=st.session_state.messages)

    print(f"✅ Case Law Prompt: {user_prompt}")

    system_message = SystemMessage(content=system_prompt)
    user_message = HumanMessage(content=user_prompt)
    
    # Add the system and user messages to the chat history
    chat_history.add_message(system_message)
    chat_history.add_message(user_message)

    # Use the correct method to call the LLM
    response = llm([system_message, user_message])

    # The response from llm should be an AIMessage object
    if isinstance(response, AIMessage):
        response_content = response.content.strip()
    else:
        raise Exception(f"Unexpected response type: {type(response)}")
    
    # Add the AI's response to the chat history
    chat_history.add_message(AIMessage(content=response_content))

    return AIMessage(content=response_content)







def get_opposition_arguments(which_side, party_names):
    # Function to look up case laws based on the last point discussed in the conversation

    # Formulate the case law query prompt
    system_template = PromptTemplate.from_template(OPPOSITIONS_ARGUMENTS_SYSTEM_PROMPT_TEMPLATE)
    user_template = PromptTemplate.from_template(OPPOSITIONS_ARGUMENTS_PROMPT_TEMPLATE)
    
    system_prompt = system_template.format(party=party_names, side=which_side)
    user_prompt = user_template.format(chat_history=st.session_state.messages)

    print(f"✅ Opposition Research Prompt: {user_prompt}")

    system_message = SystemMessage(content=system_prompt)
    user_message = HumanMessage(content=user_prompt)
    
    # Add the system and user messages to the chat history
    chat_history.add_message(system_message)
    chat_history.add_message(user_message)

    # Use the correct method to call the LLM
    response = llm([system_message, user_message])

    # The response from llm should be an AIMessage object
    if isinstance(response, AIMessage):
        response_content = response.content.strip()
    else:
        raise Exception(f"Unexpected response type: {type(response)}")
    
    # Add the AI's response to the chat history
    chat_history.add_message(AIMessage(content=response_content))

    return AIMessage(content=response_content)