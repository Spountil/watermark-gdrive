from flask import Flask, request, jsonify
import os
import sys
import logging
from dotenv import load_dotenv
import threading
import firebase_admin
from functions.gdrive_file_handler import gdrive_file_handler
from functions.webhook_check import sync_check
from webhook_subscribe import webhook_subscribe
from webhook_unsubscribe import webhook_unsubscribe


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
        webhook_unsubscribe()
        logging.info("Unsubscribed from current webhook to avoid duplicated POST.")
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

    if sync_check(message_number, 'request_message', channel_id, 'last_number'):
        return jsonify(response_data), status_code
        
    # Authentification check
    if not os.environ.get('CHANNEL_TOKEN') or channel_token != os.environ.get('CHANNEL_TOKEN'):
        logging.error(f"Security error: X-Goog-Channel-Token incorrect. Expected: '{os.environ.get('CHANNEL_TOKEN')}', Received: '{channel_token}'")
        response_data = {"error": "Unauthorized webhook token"}
        status_code = 403 # Return 403 Forbidden if the token does not match.
        return jsonify(response_data), status_code

    if resource_state == 'sync':
        logging.info(f"Webhook sync acknowledged for resource {resource_id}.")
        return jsonify({"status": "sync_acknowledged"}), 200

    thread_args = (resource_id, resource_state, FILE_SAVE_PATH)
    thread = threading.Thread(target=gdrive_file_handler, args=thread_args)
    thread.start() # Start the thread

    logging.info(f"Webhook request {resource_id} accepted, handling it in a thread.")
    return jsonify(response_data), status_code # Send back a response immediately to acknowledge the webhook request.


if __name__ == '__main__':
    load_dotenv()

    try:
        firebase_admin.initialize_app()
    except ValueError:
        None

    FILE_SAVE_PATH = os.getcwd() + '/files/downloaded_files/' 

    USER_TO_IMPERSONATE = None
    drive_service_receiver = None

    app.run(host="0.0.0.0", port=8080, debug=True)

