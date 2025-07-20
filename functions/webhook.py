from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import uuid
import json
import os
from dotenv import load_dotenv
import logging

SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/drive.readonly']

USER_TO_IMPERSONATE = None 
DRIVE_SHARED_ID = None

load_dotenv()

def get_drive_service():
    logging.info("Initialisation of Google Drive service for the receiver.")
    creds = None
    # The file token.json stores the user's access and refresh tokens.
    if os.path.exists(os.getenv('TOKEN_PATH')):
        try:
            creds = Credentials.from_authorized_user_file(os.getenv('TOKEN_PATH'), SCOPES)
        except Exception as e:
            logging.info(f"Error loading credentials from {os.getenv('TOKEN_PATH')}: {e}")
            logging.info("You may need to delete the token.json file and re-authenticate.")
            return None

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logging.info("Credentials have expired. Refreshing token...")
            try:
                creds.refresh(Request())
            except Exception as e:
                logging.info(f"Error refreshing token: {e}")
                logging.info("Re-authentication is required.")
                # Fallback to re-authentication
                flow = InstalledAppFlow.from_client_secrets_file(os.getenv('SERVICE_ACCOUNT_FILE'), SCOPES)
                creds = flow.run_local_server(port=0)
        else:
            logging.info("No valid credentials found. Starting authentication flow...")
            # This will open a browser window for the user to grant consent.
            flow = InstalledAppFlow.from_client_secrets_file(os.getenv('SERVICE_ACCOUNT_FILE'), SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open(os.getenv('TOKEN_PATH'), 'w') as token:
            token.write(creds.to_json())
            logging.info(f"Credentials saved to {os.getenv('TOKEN_PATH')}")

    drive_service_receiver = build('drive', 'v3', credentials=creds)

    return drive_service_receiver
    

def create_drive_changes_webhook_channel(service, webhook_url, start_page_token, channel_token=None, drive_id=None) -> dict:
    """Create a webhook channel for Drive changes."""
    channel_id = str(uuid.uuid4()) # Create a unique channel ID

    body = {
        'id': channel_id,
        'type': 'web_hook',
        'address': webhook_url,
    }
    if channel_token:
        body['token'] = channel_token

    try:
        if drive_id:
            # To monitor changes for a specific Shared Drive
            request = service.changes().watch(
                pageToken=start_page_token,
                body=body,
                driveId=drive_id,
                supportsAllDrives=True
            )
        else:
            # To monitor changes for the user's personal Drive
            request = service.changes().watch(
                pageToken=start_page_token,
                body=body,
                supportsAllDrives=True 
            )
        response = request.execute()

        logging.info("Webhook channel created successfully for Drive changes.")
        logging.info(f"Channel ID : {response.get('id')}")
        logging.info(f"ID of the resource : {response.get('resourceId')}")
        logging.info(f"Expiration (timestamp) : {response.get('expiration')}")
        logging.info(f"Complete information : {json.dumps(response, indent=2)}")
        
        return response
    
    except Exception as e:
        logging.info(f"Error when creating the webhook channel : {e}")
        return None
    

def stop_drive_webhook_channel(service, channel_id, resource_id) -> bool:
    """Stop the webhook channel."""
    body = {
        'id': channel_id,
        'resourceId': resource_id
    }
    try:
        # The stop call does not return a body, just a 204 No Content status on success.
        service.channels().stop(body=body).execute()
        logging.info(f"Webhook channel '{channel_id}' for the resource '{resource_id}' successfully stopped.")
        return True
    except Exception as e:
        logging.info(f"Error when stopping the webhook channel : {e}")
        return False