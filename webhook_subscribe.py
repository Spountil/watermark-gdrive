from dotenv import load_dotenv
import json
import os
import logging
import sys
from functions.webhook import get_drive_service, create_drive_changes_webhook_channel
from functions.gdrive_token import get_current_start_page_token

DRIVE_SHARED_ID = None

root = logging.getLogger()
root.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
root.addHandler(handler)

def webhook_subscribe():
    drive_service = get_drive_service()

    logging.info(f"Getting current startPageToken for Shared Drive ID: {DRIVE_SHARED_ID}")
    current_token = get_current_start_page_token(drive_service, drive_id=DRIVE_SHARED_ID)

    if current_token:
        logging.info(f"Current startPageToken: {current_token}")
        # 4. Créer le canal de notification pour les changements
        response = create_drive_changes_webhook_channel(
            drive_service,
            os.getenv('WEBHOOK_URL'),
            current_token,
            os.getenv('CHANNEL_TOKEN'),
            DRIVE_SHARED_ID
        )

        with open('./files/webhook_response.json', 'w') as f:
            json.dump(response, f)
            
    else:
        logging.info("Cannot get startPageToken. Webhook was not created.")


if __name__ == "__main__":
    load_dotenv()

    webhook_subscribe()