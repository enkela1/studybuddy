from openai import OpenAI
import os
from dotenv import load_dotenv
import time
import logging
from pathlib import Path

# Load API key from .env file
load_dotenv()

# Initialize the client with proper capitalization.
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
model = "gpt-4-1106-preview"

# Step 1. Upload your file (for reference purposes; this might still be needed for some operations)
filepath = './cryptocurrency.pdf'
with open(filepath, "rb") as f:
    file_object = client.files.create(
        file=f,
        purpose="assistants"
    )

# Step 2. Create a vector store to process and enable retrieval from your file.
vector_store = client.vector_stores.create(
    name="StudyBuddyVectorStore"
)

# Step 3. Upload the file into the vector store.
# Note: Instead of passing the file ID (which is a string), we pass the file's path as a Path-like object.
client.vector_stores.file_batches.upload_and_poll(
    vector_store_id=vector_store.id,
    files=[Path(filepath)]
)

# Step 4. Create the assistant.
# Instead of using the old "retrieval" type and 'file_ids', we now use the "file_search" tool
# and specify the vector store IDs in tool_resources.
assistant = client.beta.assistants.create(
    name="Study Buddy",
    instructions="""You are a helpful study assistant who knows a lot about understanding research papers.
Your role is to summarize papers, clarify terminology within context, and extract key figures and data.
Cross-reference information for additional insights and answer related questions comprehensively.
Analyze the papers, noting strengths and limitations.
Respond to queries effectively, incorporating feedback to enhance your accuracy.
Handle data securely and update your knowledge base with the latest research.
Adhere to ethical standards, respect intellectual property, and provide users with guidance on any limitations.
Maintain a feedback loop for continuous improvement and user support.
Your ultimate goal is to facilitate a deeper understanding of complex scientific material, making it more accessible and useful.""",
    tools=[{"type": "file_search"}],
    model=model,
    tool_resources={
        "file_search": {
            "vector_store_ids": [vector_store.id]
        }
    }
)
#
# Print the assistant ID to confirm creation
assis_id = assistant.id
print("Assistant ID:", assis_id)

# Step 5. Create a thread for interacting with the assistant.
thread = client.beta.threads.create()
thread_id = thread.id
print("Thread ID:", thread_id)




# === Harcode Assistants ID and Thread ID


message = "What is mining, based on the document?"

message = client.beta.threads.messages.create(
    thread_id=thread_id, role="user", content=message
)


# Step 6. Run the assistant in the thread with additional instructions.
run = client.beta.threads.runs.create(
    thread_id=thread_id,
    assistant_id=assis_id,
    instructions="Please address the user as Bruce"
)


def wait_for_run_completion(client, thread_id, run_id, sleep_interval=5):
    """
    Waits for a run to complete and prints the elapsed time.:param client: The OpenAI client object.
    :param thread_id: The ID of the thread.
    :param run_id: The ID of the run.
    :param sleep_interval: Time in seconds to wait between checks.
    """
    while True:
        try:
            run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
            if run.completed_at:
                elapsed_time = run.completed_at - run.created_at
                formatted_elapsed_time = time.strftime(
                    "%H:%M:%S", time.gmtime(elapsed_time)
                )
                print(f"Run completed in {formatted_elapsed_time}")
                logging.info(f"Run completed in {formatted_elapsed_time}")
                # Get messages here once Run is completed!
                messages = client.beta.threads.messages.list(thread_id=thread_id)
                last_message = messages.data[0]
                response = last_message.content[0].text.value
                print(f"Assistant Response: {response}")
                break
        except Exception as e:
            logging.error(f"An error occurred while retrieving the run: {e}")
            break
        logging.info("Waiting for run to complete...")
        time.sleep(sleep_interval)


# == Run it
wait_for_run_completion(client=client, thread_id=thread_id, run_id=run.id)


