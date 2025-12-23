import psycopg2
import os
import numpy as np
from sentence_transformers import SentenceTransformer
import re
import pickle

# --- Database Configuration ---
DB_NAME = os.environ.get("DB_NAME", "email_db")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "mysecretpassword") # Use the password you set
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5433") # Use the updated port

# --- Model Configuration ---
EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2'
CLASSIFIER_FILE = 'category_classifier.pkl'

# --- Sample Data ---
SAMPLE_EMAILS = [
    {
        "sender": "no-reply@alerts.google.com",
        "recipient": "user@example.com",
        "subject": "Critical security alert for your linked account",
        "body": "A new device signed into your Google Account. If this wasn't you, please secure your account immediately.",
    },
    {
        "sender": "newsletter@techcrunch.com",
        "recipient": "user@example.com",
        "subject": "This Week in AI: GPT-5 Rumors and New Open Source Models",
        "body": "Explore the latest developments in artificial intelligence, including breakthroughs in large language models and new open-source alternatives.",
    },
    {
        "sender": "support@your-saas.com",
        "recipient": "user@example.com",
        "subject": "Your subscription is expiring soon",
        "body": "Your monthly subscription to our service will automatically renew in 3 days. To manage your subscription, please visit your account settings.",
    }
]

def preprocess_text(text):
    if not text: return ""
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s]', '', text)
    return text.strip()

def ingest_data():
    conn = None
    try:
        # Load the trained classifier model
        print(f"Loading classifier model from '{CLASSIFIER_FILE}'...")
        with open(CLASSIFIER_FILE, 'rb') as f:
            classifier_model = pickle.load(f)
        print("Classifier loaded successfully.")

        # Connect to the database
        print("Connecting to the PostgreSQL database...")
        conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT
        )
        cur = conn.cursor()

        # Load the sentence transformer model
        print(f"Loading sentence transformer model: '{EMBEDDING_MODEL_NAME}'...")
        embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        print("Embedding model loaded successfully.")

        print("\nProcessing and ingesting emails...")
        for email in SAMPLE_EMAILS:
            subject = preprocess_text(email.get("subject", ""))
            body = preprocess_text(email.get("body", ""))
            
            # Combine subject and body for both classification and embedding
            full_text_for_classification = f"Subject: {email.get('subject', '')} Body: {email.get('body', '')}"
            full_text_for_embedding = f"Subject: {subject} Body: {body}"

            # Predict the category using the trained model
            predicted_category = classifier_model.predict([full_text_for_classification])[0]
            print(f"  - Email from '{email['sender']}' -> Predicted Category: '{predicted_category}'")
            
            # Generate the vector embedding
            embedding = embedding_model.encode(full_text_for_embedding)
            embedding_list = embedding.tolist()

            # Insert into the database with the predicted tag
            cur.execute(
                """
                INSERT INTO emails (sender, recipient, subject, body, tags, embedding)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    email["sender"],
                    email["recipient"],
                    email["subject"],
                    email["body"],
                    [predicted_category], # Add the predicted category as a tag
                    embedding_list
                )
            )

        conn.commit()
        print("\nData ingestion complete.")

    except FileNotFoundError:
        print(f"Error: Model file '{CLASSIFIER_FILE}' not found. Please run train_classifier.py first.")
    except psycopg2.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()
            print("Database connection closed.")

if __name__ == "__main__":
    ingest_data()
