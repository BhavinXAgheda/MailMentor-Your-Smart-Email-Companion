import os
import sys
import psycopg2
import numpy as np
from psycopg2.extras import RealDictCursor
from sentence_transformers import SentenceTransformer
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from pgvector.psycopg2 import register_vector
from celery.result import AsyncResult

# Import the Celery task AND the celery app instance itself
from tasks import summarize_email, celery as celery_app

# --- Configuration ---
load_dotenv()

DB_NAME = os.getenv("DB_NAME", "email_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "mysecretpassword")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5433")

# --- Model Loading ---
print("Loading sentence transformer model...")
try:
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    print("Model loaded successfully.")
except Exception as e:
    print(f"CRITICAL: Failed to load SentenceTransformer model: {e}", file=sys.stderr)
    sys.exit(1)

# --- Flask App Initialization ---
app = Flask(__name__)

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"Error: Could not connect to the database: {e}", file=sys.stderr)
        return None

# --- API Endpoints ---

@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('index.html')

@app.route('/api/search', methods=['POST'])
def search_emails():
    """Receives a query and performs a similarity search."""
    data = request.get_json()
    if not data or 'query' not in data:
        return jsonify({"error": "Missing 'query' in request body"}), 400

    query = data['query']
    print(f"Received search query: '{query}'")
    query_embedding = embedding_model.encode(query).tolist()

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    register_vector(conn)

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, sender, subject, body, timestamp, tags, embedding <=> %s AS distance FROM emails ORDER BY distance ASC LIMIT 5;",
                (np.array(query_embedding),)
            )
            results = cur.fetchall()
            print(f"Found {len(results)} matching emails.")
            return jsonify(results)
    except Exception as e:
        print(f"An error occurred during search: {e}", file=sys.stderr)
        return jsonify({"error": "An internal error occurred during search."}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/summarize/<int:email_id>', methods=['POST'])
def start_summarization_task(email_id):
    """Starts the background task to summarize an email."""
    print(f"Received request to summarize email ID: {email_id}")
    task = summarize_email.delay(email_id)
    return jsonify({"task_id": task.id}), 202

@app.route('/api/task-status/<string:task_id>', methods=['GET'])
def get_task_status(task_id):
    """Checks the status of a Celery task."""
    # FIX: Pass our configured celery_app to AsyncResult
    task_result = AsyncResult(task_id, app=celery_app)
    result = {
        "task_id": task_id,
        "status": task_result.status,
        "result": task_result.result if task_result.ready() else None
    }
    return jsonify(result)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
