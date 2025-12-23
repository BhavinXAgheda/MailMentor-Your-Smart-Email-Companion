import os
import psycopg2
from psycopg2.extras import RealDictCursor
from celery import Celery
from dotenv import load_dotenv

# --- LlamaIndex Imports ---
from llama_index.llms.ollama import Ollama
from llama_index.core import Document, Settings

# --- Configuration ---
load_dotenv()

# Celery configuration
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

# Database configuration
DB_NAME = os.getenv("DB_NAME", "email_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "mysecretpassword")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5433")

# Ollama LLM configuration
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "llama3")
OLLAMA_REQUEST_TIMEOUT = 120.0 # Increased timeout for potentially long summaries

# --- Initialize Celery ---
celery = Celery(__name__, broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)

# --- Initialize LlamaIndex LLM ---
# This sets up our connection to the local Ollama model
llm = Ollama(model=LLM_MODEL_NAME, request_timeout=OLLAMA_REQUEST_TIMEOUT)
Settings.llm = llm # Set the LLM globally for LlamaIndex components

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    try:
        return psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT
        )
    except psycopg2.OperationalError as e:
        print(f"Error: Could not connect to the database: {e}")
        return None

@celery.task(name='tasks.summarize_email')
def summarize_email(email_id):
    """
    Fetches an email by its ID, sends its content to an LLM for summarization
    using LlamaIndex, and returns the summary.
    """
    print(f"Celery task started: Summarize email with ID {email_id}")
    conn = get_db_connection()
    if not conn:
        return {"status": "error", "message": "Database connection failed in Celery task."}

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT subject, body FROM emails WHERE id = %s", (email_id,))
            email = cur.fetchone()

        if not email:
            return {"status": "error", "message": f"Email with ID {email_id} not found."}

        # Prepare the content for LlamaIndex
        email_content = f"Subject: {email['subject']}\n\nBody: {email['body']}"
        
        # Create a LlamaIndex Document object
        document = Document(text=email_content)
        
        # Define a clear, specific prompt for the LLM
        prompt = f"Provide a concise, one-sentence summary of the following email."
        
        print("Sending prompt to Ollama via LlamaIndex...")
        
        # Use the LLM to get a direct completion for the summarization task
        response = llm.complete(f"{prompt}\n\n---\n{document.text}\n---")
        
        summary = response.text.strip()
        print(f"Received summary from LlamaIndex/Ollama: {summary}")
        
        return {"status": "success", "summary": summary}

    except Exception as e:
        print(f"An error occurred in the Celery task: {e}")
        return {"status": "error", "message": f"An internal error occurred: {str(e)}"}
    finally:
        if conn:
            conn.close()
