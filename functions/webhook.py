from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import uuid
import json
import os
from dotenv import load_dotenv
import logging
import google.auth

SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/drive.readonly']

USER_TO_IMPERSONATE = None 
DRIVE_SHARED_ID = None

load_dotenv()

def get_drive_service():
    logging.info("Initialisation du service Google Drive pour le récepteur.")
    # Obtient les identifiants par défaut du compte de service associé à la Cloud Run instance.
    # C'est la méthode recommandée pour l'authentification des services GCP.
    creds = None
    # The file token.json stores the user's access and refresh tokens.
    if os.path.exists(os.getenv('TOKEN_PATH')):
        try:
            creds = Credentials.from_authorized_user_file(os.getenv('TOKEN_PATH'), SCOPES)
        except Exception as e:
            print(f"Error loading credentials from {os.getenv('TOKEN_PATH')}: {e}")
            print("You may need to delete the token.json file and re-authenticate.")
            return None

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Credentials have expired. Refreshing token...")
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Error refreshing token: {e}")
                print("Re-authentication is required.")
                # Fallback to re-authentication
                flow = InstalledAppFlow.from_client_secrets_file(os.getenv('SERVICE_ACCOUNT_FILE'), SCOPES)
                creds = flow.run_local_server(port=0)
        else:
            print("No valid credentials found. Starting authentication flow...")
            # This will open a browser window for the user to grant consent.
            flow = InstalledAppFlow.from_client_secrets_file(os.getenv('SERVICE_ACCOUNT_FILE'), SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open(os.getenv('TOKEN_PATH'), 'w') as token:
            token.write(creds.to_json())
            print(f"Credentials saved to {os.getenv('TOKEN_PATH')}")

    drive_service_receiver = build('drive', 'v3', credentials=creds)

    return drive_service_receiver


def get_current_start_page_token(service, drive_id=None):
    """Récupère le startPageToken actuel."""
    try:
        if drive_id:
            # Pour un Drive Partagé
            response = service.changes().getStartPageToken(
                driveId=drive_id,
                supportsAllDrives=True
            ).execute()
        else:
            # Pour l'utilisateur (inclut les dossiers personnels)
            response = service.changes().getStartPageToken(
                supportsAllDrives=True # Important pour inclure les Drives partagés accessibles à l'utilisateur
            ).execute()
        return response.get('startPageToken')
    except Exception as e:
        print(f"Erreur lors de la récupération du startPageToken : {e}")
        return None
    

def create_drive_changes_webhook_channel(service, webhook_url, start_page_token, channel_token=None, drive_id=None):
    """Crée un canal de notification (webhook) pour les changements."""
    channel_id = str(uuid.uuid4()) # Génère un ID de canal unique

    body = {
        'id': channel_id,
        'type': 'web_hook',
        'address': webhook_url,
    }
    if channel_token:
        body['token'] = channel_token

    try:
        if drive_id:
            # Pour surveiller les changements dans un Drive Partagé spécifique
            request = service.changes().watch(
                pageToken=start_page_token,
                body=body,
                driveId=drive_id,
                supportsAllDrives=True # Indique que la requête supporte les Drives partagés
            )
        else:
            # Pour surveiller les changements pour l'utilisateur (inclut ses dossiers personnels)
            request = service.changes().watch(
                pageToken=start_page_token,
                body=body,
                supportsAllDrives=True # Indique que la requête supporte les Drives partagés accessibles à l'utilisateur
            )
        response = request.execute()

        print(f"Canal de webhook créé avec succès pour les changements.")
        print(f"ID du canal : {response.get('id')}")
        print(f"ID de la ressource : {response.get('resourceId')}")
        print(f"Expiration (timestamp) : {response.get('expiration')}")
        print(f"Informations complètes : {json.dumps(response, indent=2)}")
        
        return response
    
    except Exception as e:
        print(f"Erreur lors de la création du canal de webhook : {e}")
        return None
    

def stop_drive_webhook_channel(service, channel_id, resource_id):
    """Arrête un canal de notification (webhook)."""
    body = {
        'id': channel_id,
        'resourceId': resource_id
    }
    try:
        # L'appel à stop() ne renvoie pas de corps, juste un statut 204 No Content en cas de succès.
        service.channels().stop(body=body).execute()
        print(f"Canal de webhook '{channel_id}' pour la ressource '{resource_id}' arrêté avec succès.")
        return True
    except Exception as e:
        print(f"Erreur lors de l'arrêt du canal de webhook : {e}")
        return False