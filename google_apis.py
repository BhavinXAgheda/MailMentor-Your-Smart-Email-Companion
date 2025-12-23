import os
import traceback
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

def create_service(client_secret_file, api_name, api_version, scopes, prefix=''):
    CLIENT_SECRET_FILE = client_secret_file
    API_SERVICE_NAME = api_name
    API_VERSION = api_version
    SCOPES = scopes
    creds = None

    working_dir = os.getcwd()
    token_dir = 'token files'
    token_file = f'token_{API_SERVICE_NAME}_{API_VERSION}{prefix}.json'
    token_path = os.path.join(working_dir, token_dir, token_file)

    # Ensure token directory exists
    if not os.path.exists(os.path.join(working_dir, token_dir)):
        os.mkdir(os.path.join(working_dir, token_dir))

    # Load existing credentials
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    # Handle expired/invalid credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print("❌ Failed to refresh credentials:", e)
        else:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
            except Exception as e:
                print("❌ OAuth flow failed:")
                traceback.print_exc()
                return None

        # Save new token
        with open(token_path, 'w') as token:
            token.write(creds.to_json())

    # Try to build the service
    try:
        service = build(API_SERVICE_NAME, API_VERSION, credentials=creds, static_discovery=False)
        print(f"✅ {API_SERVICE_NAME} {API_VERSION} service created successfully.")
        return service

    except Exception as e:
        print("❌ Exception while creating Gmail service:")
        traceback.print_exc()
        print(f'⚠️ Failed to create service instance for {API_SERVICE_NAME}')
        if os.path.exists(token_path):
            os.remove(token_path)
        return None
