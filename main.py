from flask import Flask, request, jsonify
import os
import sys
import logging
from dotenv import load_dotenv
import threading
from functions.webhook import get_drive_service
from functions.gdrive_token import load_startpagetoken, save_startpagetoken
from functions.gdrive_file_handler import gdrive_file_handler
from webhook_subscribe import webhook_subscribe

root = logging.getLogger()
root.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
root.addHandler(handler)

app = Flask(__name__)

SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/drive.readonly']

drive_service_receiver = None


@app.route('/', methods=['GET'])
def landing_page():
    token = request.headers.get('WHO-ARE-YOU')

    if os.getenv('CHANNEL_TOKEN') == token:
        logging.info("Received a valid token in the GET request.")
        webhook_subscribe()
        logging.info("Webhook subscription initiated.")

        name = f"""
        Received a GET request on the root endpoint.
        Subscribing to the webhook with the token.
        """
    else:
        name = f"""
        Received a GET request on the root endpoint.
        Hello World.
        """

    return name, 200


@app.route('/webhook', methods=['POST'])
def webhook():

    response_data = {"status": "received", "message": "Processing in background"}
    status_code = 202 # 202 Accepted to indicate that the request has been accepted for processing, but the processing is not complete.

    channel_id = request.headers.get('X-Goog-Channel-ID') # ID of the channel that received the notification.
    resource_id = request.headers.get('X-Goog-Resource-ID') # ID of the resource that changed (e.g., a Shared Drive ID).
    resource_state = request.headers.get('X-Goog-Resource-State') # State of the resource (ex: 'change', 'sync', 'trash').
    channel_token = request.headers.get('X-Goog-Channel-Token') # Secret token given when subscribing to the webhook.
    message_number = request.headers.get('X-Goog-Message-Number') # Number of the message in the channel.
    
    logging.info(f"Webhook Headers: ChannelID={channel_id}, ResourceID={resource_id}, State={resource_state}, Token={channel_token}, MsgNum={message_number}")
    logging.info(f"Webhook Body (usually empty): {request.data.decode('utf-8', errors='ignore')}")

    # Authentification check
    if not os.environ.get('CHANNEL_TOKEN') or channel_token != os.environ.get('CHANNEL_TOKEN'):
        logging.error(f"Security error: X-Goog-Channel-Token incorrect. Expected: '{os.environ.get('CHANNEL_TOKEN')}', Received: '{channel_token}'")
        response_data = {"error": "Unauthorized webhook token"}
        status_code = 403 # Return 403 Forbidden if the token does not match.
        return jsonify(response_data), status_code

    if resource_state == 'sync':
        logging.info(f"Webhook sync acknowledged for resource {resource_id}.")
        return jsonify({"status": "sync_acknowledged"}), 200

    drive_service = get_drive_service()
    
    last_token = load_startpagetoken(resource_id, local, local_token_file=LOCAL_TOKEN_DB_FILE if local else None)
        
    try:
        last_token = last_token[resource_id].get('token')
    except KeyError:
        pass

    if not last_token:
        logging.warning(f"No previous startPageToken found for resource {resource_id}. Attempting to retrieve the current token.")
        start_page_token_response = drive_service.changes().getStartPageToken(supportsAllDrives=True).execute()
        last_token = start_page_token_response.get('startPageToken')
        save_startpagetoken(resource_id, last_token, local, local_token_file=LOCAL_TOKEN_DB_FILE if local else None) # Sauvegarde ce token initial pour les futures exécutions.
        logging.info(f"Initial startPageToken retrieved and saved for {resource_id}: {last_token}")
    
    logging.info(f"Recovering changes from token: {last_token} for resource {resource_id}")
        
    # Check if the resource_id is a Shared Drive ID.
    # Shared Drive IDs are typically 33 characters long.
    is_shared_drive_resource = len(resource_id) == 33 

    # Call the `changes().list()` method to get the actual list of changes.
    results = drive_service.changes().list(
        pageToken=last_token,
        supportsAllDrives=True,
        includeRemoved=True,
        driveId=resource_id if is_shared_drive_resource else None, 
        fields="nextPageToken,newStartPageToken,changes(fileId,file(name,parents,mimeType,trashed,shared,size))"
    ).execute()

    changes = results.get('changes', [])
    new_start_page_token = results.get('newStartPageToken')

    if new_start_page_token:
        save_startpagetoken(resource_id, new_start_page_token, local, local_token_file=LOCAL_TOKEN_DB_FILE if local else None)
        logging.info(f"startPageToken updated to : {new_start_page_token} for resource {resource_id}")

    thread_args = (resource_id, resource_state, drive_service, changes, FILE_SAVE_PATH)
    thread = threading.Thread(target=gdrive_file_handler, args=thread_args)
    thread.start() # Start the thread

    logging.info(f"Webhook request {resource_id} accepted, handling it in a thread.")
    return jsonify(response_data), status_code # Send back a response immediately to acknowledge the webhook request.


if __name__ == '__main__':
    load_dotenv()

    FILE_SAVE_PATH = os.getcwd() + '/files/downloaded_files/' 

    try:
        from google.cloud import firestore
        firestore_client = firestore.Client() 
        local = False
        logging.info("Firestore client initialized successfully.")
    except ImportError:
        USER_TO_IMPERSONATE = None
        LOCAL_TOKEN_DB_FILE = './files/local_webhook_tokens.json'
        drive_service_receiver = None
        local = True
        logging.info("Firestore client could not be imported. Using local JSON file for tokens.")

    if local:
        app.run(host="0.0.0.0", port=8080, debug=True)
    else:
        port = int(os.environ.get("PORT", 8080))
        app.run(host="0.0.0.0", port=port)

