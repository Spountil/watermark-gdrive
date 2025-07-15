from functions.webhook import *
import json

if __name__ == "__main__":
    load_dotenv()

    # 1. Obtenir les identifiants
    drive_service = get_drive_service(local=True)

    with open('webhook_response.json') as f:
        response = json.load(f)

    CHANNEL_TO_STOP_ID = response['id']
    RESOURCE_TO_STOP_ID = response['resourceId']

    # 3. Arrêter le canal de notification
    print(f"Tentative d'arrêt du canal : {CHANNEL_TO_STOP_ID} pour la ressource : {RESOURCE_TO_STOP_ID}")
    stop_drive_webhook_channel(drive_service, CHANNEL_TO_STOP_ID, RESOURCE_TO_STOP_ID)



