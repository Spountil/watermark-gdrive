import firebase_admin
from firebase_admin import firestore
import logging

try:
    firebase_admin.initialize_app()
except ValueError:
    None

db = firestore.client()


def sync_check(message_number, collection_name, document_name, dict_name):

    message_number = int(message_number)

    last_message_info = db.collection(collection_name).document(document_name)

    try:
        last_message_number = int(last_message_info.get().to_dict()[dict_name])
    except Exception:
        last_message_number = 0

    if message_number < last_message_number:
        logging.error(f"{collection_name} - Message number {message_number} has already been processed. Ignoring duplicate.")
        return True
    else:
        last_message_info.set({dict_name: message_number})
        logging.info(f"{collection_name} - Message number {message_number} recorded as last processed message.")
        return False
    
    
if __name__ == "__main__":
    sync_check(1)