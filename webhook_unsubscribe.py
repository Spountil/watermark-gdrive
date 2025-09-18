import json
import logging
import sys
from dotenv import load_dotenv
from functions.webhook import get_drive_service, stop_drive_webhook_channel

root = logging.getLogger()
root.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
root.addHandler(handler)

def webhook_unsubscribe():
    """Unsubscribe from the current webhook channel."""

    drive_service = get_drive_service()

    with open('./files/webhook_response.json') as f:
        response = json.load(f)

    CHANNEL_TO_STOP_ID = response['id']
    RESOURCE_TO_STOP_ID = response['resourceId']


    logging.info(f"Chanel stop attempt {CHANNEL_TO_STOP_ID} for resource : {RESOURCE_TO_STOP_ID}")
    stop_drive_webhook_channel(drive_service, CHANNEL_TO_STOP_ID, RESOURCE_TO_STOP_ID)


if __name__ == "__main__":
    load_dotenv()

    webhook_unsubscribe()



