import firebase_admin
from firebase_admin import firestore
import logging


def webhook_check(message_number):
    try:
        app = firebase_admin.initialize_app()
    except ValueError:
        None

    db = firestore.client()
    last_message_info = db.collection("request_message").document("last_message")

    try:
        last_message_number = last_message_info.get().to_dict()['last_number']
    except Exception:
        last_message_number = 0

    if message_number == last_message_number:
        logging.error(f"Message number {message_number} has already been processed. Ignoring duplicate.")
        return True
    else:
        last_message_info.set({"last_number": message_number})
        logging.info(f"Message number {message_number} recorded as last processed message.")
        return False
    
    
if __name__ == "__main__":
    webhook_check(1)