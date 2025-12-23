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
#database
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


Base.metadata.create_all(bind=engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


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
            # Check for duplicates within the current batch
            if current_message_id in processed_ids:
                continue

            # Check if an email with the same message_id already exists in the DB
            exists = db_session.query(Email.id).filter_by(message_id=current_message_id).first()
            if exists:
                continue
            
            processed_ids.add(current_message_id)
            new_email = Email(**email_data) # Unpack dictionary to model
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
            # Recursive call for multipart messages
            if part.get('parts'):
                body = get_message_body(part)
                if body:
                    return body
    elif 'body' in payload and 'data' in payload['body']:
         if payload['mimeType'] == 'text/plain':
            return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')

    return "(No plain text body found)"


def fetch_new_emails(service, max_results=10):
    """
    Fetches new emails from Gmail and returns them as a list of dictionaries.
    """
    try:
        # Fetch a list of recent messages. The database will handle duplicates.
        response = service.users().messages().list(
            userId='me',
            labelIds=['INBOX'],
            maxResults=max_results,
            q='is:unread' # A good way to only get new messages
        ).execute()

        messages = response.get('messages', [])
        if not messages:
            return []

        print(f"📥 Found {len(messages)} unread email(s). Parsing details...")
        
        parsed_emails = []
        for msg in messages:
            msg_data = service.users().messages().get(
                userId='me', id=msg['id'], format='full').execute()
            
            headers = msg_data['payload'].get('headers', [])
            
            email_dict = {
                'message_id': msg_data.get('id'),
                'recipient': '(not available)' # Recipient is often in the 'To' header
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
                    # Parse the date string into a timezone-aware datetime object
                    email_dict['received_date'] = parsedate_to_datetime(header['value'])

            email_dict['body'] = get_message_body(msg_data['payload'])
            parsed_emails.append(email_dict)
        
        return parsed_emails

    except HttpError as error:
        print(f"❌ Gmail API error: {error}")
        return []


def main():
    """Main function to run the continuous polling service."""
    service = create_service(CLIENT_SECRET_FILE, API_SERVICE_NAME, API_VERSION, SCOPES)
    if not service:
        print("❌ Could not initialize Gmail service. Exiting.")
        return

    print("🚀 Service started. Checking for new emails every", POLL_INTERVAL, "seconds...")
    
    try:
        while True:
            # Step 1: Fetch new emails from the Gmail API
            new_emails = fetch_new_emails(service)

            # Step 2: If we found any, save them to the database
            if new_emails:
                save_emails_to_db(new_emails)
            else:
                print("📭 No new emails found this cycle.")
            
            # Step 3: Wait for a while before checking again
            print(f"--- Waiting for {POLL_INTERVAL} seconds... ---")
            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print("\n🛑 Service stopped by user.")


if __name__ == "__main__":
    main()