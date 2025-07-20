import os
import logging
import json
import datetime

try:
    from google.cloud import firestore
    firestore_client = firestore.Client()
except:
    logging.error("Firestore client could not be imported. Ensure the google-cloud-firestore package is installed.")
    firestore_client = None


def get_current_start_page_token(service, drive_id=None) -> str:
    """Get the current startPageToken"""
    try:
        if drive_id:
            # For a specific Shared Drive
            response = service.changes().getStartPageToken(
                driveId=drive_id,
                supportsAllDrives=True
            ).execute()
        else:
            # For the user's personal Drive
            response = service.changes().getStartPageToken(
                supportsAllDrives=True
            ).execute()
        return response.get('startPageToken')
    
    except Exception as e:
        print(f"Error - cannot get the startPageToken : {e}")
        return None
    

def load_startpagetoken(resource_id, local, local_token_file) -> dict:
    """Load the startPageToken for a given resource from Firestore or a local JSON file."""

    if local:
        if os.path.exists(local_token_file):
            with open(local_token_file, 'r') as f:
                try:
                    token_data = json.load(f)
                    logging.info(f"Token loaded for the resource {resource_id}: {token_data[resource_id].get('token')}")
                    return token_data
                except json.JSONDecodeError:
                    logging.warning(f"File {local_token_file} corrupted or empty. Return an empty dictionary.")
                    return {}
        logging.info(f"File {local_token_file} not found. Initialize a local database.")
        return {}
    
    else:
        doc_ref = firestore_client.collection('webhook_tokens').document(resource_id)
        doc = doc_ref.get()
        if doc.exists:
            token_data = doc.to_dict()
            logging.info(f"Token loaded for resource {resource_id}: {token_data.get('token')}")
            return token_data.get('token')
        logging.info(f"Token not found for resource {resource_id}. Normal for the first modification.")
        return None
    

def save_startpagetoken(resource_id, token, local, local_token_file) -> None:
    if local:
        """Save the sartPageToken to a local JSON file."""
        tokens_db = load_startpagetoken(resource_id, local, local_token_file)
        tokens_db[resource_id] = {'token': token, 'last_updated': datetime.datetime.now().isoformat()}
        with open(local_token_file, 'w') as f:
            json.dump(tokens_db, f, indent=2)
        logging.info(f"Token saved locally for resource {resource_id}: {token}")
    
    else:
        """Save the new startPageToken into Firestone."""
        doc_ref = firestore_client.collection('webhook_tokens').document(resource_id)
        doc_ref.set({'token': token, 'last_updated': firestore.SERVER_TIMESTAMP})
        logging.info(f"Token saved for resource {resource_id}: {token}")