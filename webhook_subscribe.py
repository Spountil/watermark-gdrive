from functions.webhook import *
from dotenv import load_dotenv
import json

DRIVE_SHARED_ID = None

if __name__ == "__main__":
    load_dotenv()

    print(os.getenv('SERVICE_ACCOUNT_FILE'))

    # 1. Obtenir les identifiants
    creds = get_drive_service()
    if not creds:
        print("Impossible d'obtenir les identifiants de service.")
    else:
        # 2. Construire le service Drive
        drive_service = build('drive', 'v3', credentials=creds)

        # 3. Obtenir le startPageToken actuel
        # C'est ce token qui définit le point de départ des notifications.
        # Les changements survenus AVANT ce token ne seront PAS notifiés.
        print("Récupération du startPageToken actuel...")
        current_token = get_current_start_page_token(drive_service, drive_id=DRIVE_SHARED_ID)

        if current_token:
            print(f"startPageToken actuel: {current_token}")
            # 4. Créer le canal de notification pour les changements
            response = create_drive_changes_webhook_channel(
                drive_service,
                os.getenv('WEBHOOK_URL'),
                current_token,
                os.getenv('CHANNEL_TOKEN'),
                DRIVE_SHARED_ID
            )

            with open('webhook_response.json', 'w') as f:
                json.dump(response, f)


        else:
            print("Impossible de récupérer le startPageToken. Le webhook ne peut pas être créé.")