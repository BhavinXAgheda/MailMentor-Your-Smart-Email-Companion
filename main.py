import os
from fastapi import FastAPI
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

# --- Configuration ---
# Fetching configuration from environment variables
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
QDRANT_URL = os.getenv("QDRANT_URL")
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL")

# Create an instance of the FastAPI class
app = FastAPI(
    title="MailMentor API",
    version="0.1.0"
)

@app.get("/")
def read_root():
    """
    Root endpoint to check if the API is running and configuration is loaded.
    """
    return {
        "message": "Welcome to the MailMentor API!",
        "status": "API is running",
        "database_host": DB_HOST,
        "database_port": DB_PORT,
        "qdrant_url": QDRANT_URL,
        "ollama_url": OLLAMA_URL
    }

# Next, you will add your API endpoints for search, summary, etc.
# For example:
# from your_email_module import search_emails
#
# @app.post("/api/search")
# async def api_search(query: str):
#     results = await search_emails(query)
#     return {"results": results}
