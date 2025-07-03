from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import uuid
import json
import os
import pickle
from dotenv import load_dotenv

SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/drive.readonly']

USER_TO_IMPERSONATE = None 
DRIVE_SHARED_ID = None

def get_drive_service():
    """Initialise le service Google Drive en fonction du mode d'authentification."""
    print("Utilisation du compte de service pour l'authentification.")
    return service_account.Credentials.from_service_account_file(
        os.getenv('SERVICE_ACCOUNT_FILE'), scopes=SCOPES, subject=USER_TO_IMPERSONATE
    )


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
        'address': webhook_url
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