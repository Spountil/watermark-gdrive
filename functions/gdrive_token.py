import logging
import firebase_admin
from firebase_admin import firestore

try:
    firebase_admin.initialize_app()
except ValueError:
    None

db = firestore.client()

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
    

def load_startpagetoken(resource_id) -> dict:
    """Load the startPageToken for a given resource from Firestore or a local JSON file."""

    try:
        app = firebase_admin.initialize_app()
    except ValueError:
        None

    doc_ref = db.collection('webhook_tokens').document(resource_id)
    doc = doc_ref.get()

    if doc.exists:
        token_data = doc.to_dict()
        logging.info(f"Token loaded for resource {resource_id}: {token_data.get('token')}")
        return token_data.get('token')
    
    logging.info(f"Token not found for resource {resource_id}. Normal for the first modification.")
    return None
    

def save_startpagetoken(resource_id, token) -> None:
    """Save the new startPageToken into Firestone."""

    try:
        app = firebase_admin.initialize_app()
    except ValueError:
        None

    doc_ref = db.collection('webhook_tokens').document(resource_id)
    doc_ref.set({'token': token, 'last_updated': firestore.SERVER_TIMESTAMP})
    logging.info(f"Token saved for resource {resource_id}: {token}")