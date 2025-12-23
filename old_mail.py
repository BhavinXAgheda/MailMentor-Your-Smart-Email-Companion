import os
import time
import base64
from datetime import datetime
from email.utils import parsedate_to_datetime

# --- Google API Imports ---
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_apis import create_service  # Your existing Google API service creator

# --- SQLAlchemy Imports ---
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    DateTime
)
from sqlalchemy.orm import sessionmaker, declarative_base

# ==============================================================================
# 1. CONFIGURATION
# ==============================================================================

# -- Gmail API Config --
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
CLIENT_SECRET_FILE = 'client_secret.json'
API_SERVICE_NAME = 'gmail'
API_VERSION = 'v1'

# -- Script Config --
POLL_INTERVAL = 60  # seconds

# -- Database Config --
DATABASE_URL = "postgresql://postgres:0000@localhost/email_db"

# ==============================================================================
# 2. DATABASE SETUP
# ==============================================================================

engine = create_engine(DATABASE_URL)
Base = declarative_base()

class Email(Base):
    """Email ORM Model."""
    __tablename__ = 'emails'
    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String(255), unique=True, nullable=False, index=True)
    sender = Column(String(255), nullable=False)
    recipient = Column(String(255))
    subject = Column(Text)
    body = Column(Text)
    received_date = Column(DateTime)

    def __repr__(self):
        return f"<Email(id={self.id}, from='{self.sender}', subject='{self.subject[:30]}...')>"

# Create the table if it doesn't exist
Base.metadata.create_all(bind=engine)
# Create a session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ==============================================================================
# 3. HELPER & CORE FUNCTIONS
# ==============================================================================

def save_emails_to_db(email_list: list[dict]):
    """Saves a list of parsed email dictionaries to the database."""
    if not email_list:
        return

    db_session = SessionLocal()
    processed_ids = set()
    
    print(f"  Attempting to save {len(email_list)} emails to the database...")
    try:
        for email_data in email_list:
            current_message_id = email_data['message_id']
            if current_message_id in processed_ids:
                continue

            exists = db_session.query(Email.id).filter_by(message_id=current_message_id).first()
            if exists:
                continue
            
            processed_ids.add(current_message_id)
            new_email = Email(**email_data)
            db_session.add(new_email)
        
        if not processed_ids:
            print("  All fetched emails were already in the database. Nothing new to save.")
            return

        db_session.commit()
        print(f"✅ Success! Saved {len(processed_ids)} new emails to the database.")

    except Exception as e:
        print(f"❌ An error occurred during database operation: {e}")
        db_session.rollback()
    finally:
        db_session.close()

def get_message_body(payload):
    """Parses the email payload to find the plain text body."""
    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain' and 'data' in part['body']:
                return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
            if part.get('parts'):
                body = get_message_body(part)
                if body:
                    return body
    elif 'body' in payload and 'data' in payload['body']:
         if payload['mimeType'] == 'text/plain':
            return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')

    return "(No plain text body found)"

def fetch_new_emails(service, max_results=1000):
    """
    Fetches up to `max_results` emails from Gmail and returns them as a list of dictionaries.
    Uses pagination if more than 500 emails are requested.
    """
    try:
        parsed_emails = []
        next_page_token = None
        remaining = max_results

        while remaining > 0:
            batch_size = min(remaining, 500)  # Gmail API max limit per call
            response = service.users().messages().list(
                userId='me',
                labelIds=['INBOX'],
                maxResults=batch_size,
                pageToken=next_page_token,
                q=''  # Fetch all emails, not just unread
            ).execute()

            messages = response.get('messages', [])
            if not messages:
                break

            print(f"📥 Found {len(messages)} email(s) in this batch. Parsing details...")

            for msg in messages:
                msg_data = service.users().messages().get(
                    userId='me', id=msg['id'], format='full').execute()

                headers = msg_data['payload'].get('headers', [])
                email_dict = {
                    'message_id': msg_data.get('id'),
                    'recipient': '(not available)'
                }

                for header in headers:
                    name = header['name'].lower()
                    if name == 'subject':
                        email_dict['subject'] = header['value']
                    elif name == 'from':
                        email_dict['sender'] = header['value']
                    elif name == 'to':
                        email_dict['recipient'] = header['value']
                    elif name == 'date':
                        email_dict['received_date'] = parsedate_to_datetime(header['value'])

                email_dict['body'] = get_message_body(msg_data['payload'])
                parsed_emails.append(email_dict)

                if len(parsed_emails) >= max_results:
                    break

            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break

            remaining = max_results - len(parsed_emails)

        return parsed_emails

    except HttpError as error:
        print(f"❌ Gmail API error: {error}")
        return []

# ==============================================================================
# 4. MAIN EXECUTION
# ==============================================================================

def main():
    """Fetch up to 1000 emails once and save to database."""
    service = create_service(CLIENT_SECRET_FILE, API_SERVICE_NAME, API_VERSION, SCOPES)
    if not service:
        print("❌ Could not initialize Gmail service. Exiting.")
        return

    print("🚀 Fetching up to 1000 emails from Gmail...")
    
    new_emails = fetch_new_emails(service, max_results=1000)
    if new_emails:
        save_emails_to_db(new_emails)
    else:
        print("📭 No emails found.")

if __name__ == "__main__":
    main()
