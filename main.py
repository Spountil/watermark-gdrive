from flask import Flask, request, jsonify
from google.oauth2 import service_account
import google.auth
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import os
import json
import logging
from dotenv import load_dotenv
import datetime
import threading
import io


logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/drive.readonly']

drive_service_receiver = None


def load_startpagetoken(resource_id, local):
    """Charge les startPageTokens depuis un fichier JSON local."""

    if local:
        if os.path.exists(LOCAL_TOKEN_DB_FILE):
            with open(LOCAL_TOKEN_DB_FILE, 'r') as f:
                try:
                    token_data = json.load(f)
                    logging.info(f"Token chargé pour la ressource {resource_id}: {token_data[resource_id].get('token')}")
                    return token_data
                except json.JSONDecodeError:
                    logging.warning(f"Fichier {LOCAL_TOKEN_DB_FILE} corrompu ou vide. Retourne une base de données vide.")
                    return {}
        logging.info(f"Fichier {LOCAL_TOKEN_DB_FILE} non trouvé. Initialise une nouvelle base de données locale.")
        return {}
    
    else:
        doc_ref = firestore_client.collection('webhook_tokens').document(resource_id)
        doc = doc_ref.get()
        if doc.exists:
            token_data = doc.to_dict()
            logging.info(f"Token chargé pour la ressource {resource_id}: {token_data.get('token')}")
            return token_data.get('token')
        logging.info(f"Aucun token trouvé pour la ressource {resource_id}. Ceci est normal pour la première notification.")
        return None


def save_startpagetoken(resource_id, token, local):
    if local:
        """Sauvegarde un startPageToken pour une ressource donnée dans le fichier JSON local."""
        tokens_db = load_startpagetoken(resource_id, local)
        tokens_db[resource_id] = {'token': token, 'last_updated': datetime.datetime.now().isoformat()}
        with open(LOCAL_TOKEN_DB_FILE, 'w') as f:
            json.dump(tokens_db, f, indent=2)
        logging.info(f"Token sauvegardé localement pour {resource_id}: {token}")
    
    else:
        """Sauvegarde le nouveau startPageToken pour une ressource donnée dans Firestore."""
        doc_ref = firestore_client.collection('webhook_tokens').document(resource_id)
        # Utilise firestore.SERVER_TIMESTAMP pour enregistrer le moment de la mise à jour côté serveur.
        doc_ref.set({'token': token, 'last_updated': firestore.SERVER_TIMESTAMP})
        logging.info(f"Token sauvegardé pour la ressource {resource_id}: {token}")


def get_drive_service_for_webhook_receiver(local):
    """Initialise le service Google Drive pour le récepteur de webhook en utilisant les identifiants par défaut de Cloud Run."""
    global drive_service_receiver
    global credentials

    if drive_service_receiver is None:
        logging.info("Initialisation du service Google Drive pour le récepteur.")
        # Obtient les identifiants par défaut du compte de service associé à la Cloud Run instance.
        # C'est la méthode recommandée pour l'authentification des services GCP.
        if local:
            credentials = service_account.Credentials.from_service_account_file(
            os.getenv('SERVICE_ACCOUNT_FILE'), scopes=SCOPES, subject=USER_TO_IMPERSONATE
            )
        else:
            credentials, project = google.auth.default(scopes=SCOPES) 

        drive_service_receiver = build('drive', 'v3', credentials=credentials)

    return drive_service_receiver


def download_file(drive_service, file_id, destination_path=None):
    """
    Télécharge le contenu d'un fichier depuis Google Drive.
    """
    try:
        request = drive_service.files().get(fileId=file_id, alt='media')
        file = io.BytesIO()
        downloader = MediaIoBaseDownload(file, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            logging.info(f"Progression du téléchargement de {file_id}: {int(status.progress() * 100)}%")

        file.seek(0)
        file_content = file.read()

        if destination_path:
            with open(destination_path, 'wb') as f:
                f.write(file_content)
            logging.info(f"Fichier {file_id} téléchargé et sauvegardé à : {destination_path}")
        else:
            logging.info(f"Fichier {file_id} téléchargé en mémoire.")
        return file
        
    except Exception as e:
        logging.error(f"Erreur lors du téléchargement du fichier {file_id} depuis Google Drive : {e}", exc_info=True)
        return None


def gdrive_sync_check(resource_id, resource_state, local):
    # --- 3. Traiter la notification (récupérer les détails des changements) ---
    # Le corps de la notification webhook est généralement vide ; les détails des changements doivent être récupérés via l'API Drive.
    
    logging.info(f"Début du traitement asynchrone pour la ressource : {resource_id}, état : {resource_state}")

    try:
        drive_service = get_drive_service_for_webhook_receiver(local)
        
        # Récupère le dernier startPageToken connu pour cette ressource spécifique.
        # C'est le point de départ à partir duquel nous voulons lister les nouveaux changements.
        last_token = load_startpagetoken(resource_id, local)
        
        try:
            last_token = last_token[resource_id].get('token')
        except KeyError:
            pass

        if not last_token:
            logging.warning(f"Aucun startPageToken précédent trouvé pour la ressource {resource_id}. Tentative de récupération du token actuel.")
            # Si aucun token n'est trouvé (première exécution ou réinitialisation),
            # on récupère le token actuel pour commencer à suivre les changements.
            start_page_token_response = drive_service.changes().getStartPageToken(supportsAllDrives=True).execute()
            last_token = start_page_token_response.get('startPageToken')
            save_startpagetoken(resource_id, last_token, local) # Sauvegarde ce token initial pour les futures exécutions.
            logging.info(f"Initial startPageToken retrieved and saved for {resource_id}: {last_token}")
            # À ce stade, on pourrait décider de ne pas traiter les changements pour ce premier token si l'on veut partir d'un état "vierge".
            # Pour cet exemple, le flux continue pour traiter tout changement.
        
        logging.info(f"Récupération des changements depuis le token: {last_token} pour ressource {resource_id}")
        
        # Heuristique pour déterminer si la ressource est un Shared Drive.
        # Les IDs des Shared Drives ont typiquement une longueur de 33 caractères.
        is_shared_drive_resource = len(resource_id) == 33 

        # Appelle la méthode `changes().list()` pour obtenir la liste des changements réels.
        # `pageToken` est le point de départ. `supportsAllDrives=True` est essentiel pour les Shared Drives.
        # `includeRemoved=True` pour détecter les suppressions.
        # `fields` pour limiter les données récupérées et optimiser la performance.
        results = drive_service.changes().list(
            pageToken=last_token,
            supportsAllDrives=True,
            includeRemoved=True,
            driveId=resource_id if is_shared_drive_resource else None, 
            fields="nextPageToken,newStartPageToken,changes(fileId,file(name,parents,mimeType,trashed,shared,size))"
        ).execute()

        changes = results.get('changes', [])
        new_start_page_token = results.get('newStartPageToken') # Le token à utiliser pour la prochaine requête `list()`

        if changes:
            with open('response.json', 'w') as f:
                json.dump(changes, f)
                
            logging.info(f"Nombre de changements détectés : {len(changes)}")
            for change in changes:
                file_id = change.get('fileId')
                file_info = change.get('file')
                if file_info:
                    parents = file_info.get('parents', [])
                    logging.info(f"  Changement sur fichier/dossier ID: {file_id}, Nom: {file_info.get('name')}, Parents: {parents}, État: {'Supprimé' if file_info.get('trashed') else 'Actif'}")
                    # --- Votre LOGIQUE MÉTIER ICI pour le traitement du changement ---
                    # C'est ici que vous implémenteriez la logique spécifique à votre application.
                    # Par exemple, si vous surveillez un dossier spécifique dans "Mon Drive" et non un Shared Drive entier,
                    # vous vérifieriez si l'ID de ce dossier cible est présent dans la liste des parents du fichier modifié.
                    # Example :
                    # if 'ID_DE_MON_DOSSIER_CIBLE_NORMAL' in parents:
                    #    logging.info("Ce changement concerne mon dossier cible ! Lancer le script X ou mettre à jour la DB.")
                    # Vous pourriez déclencher d'autres actions, comme envoyer une notification,
                    # mettre à jour une base de données, ou lancer un autre processus.

                    if not file_info.get('trashed'):
                        download = download_file(drive_service, file_id, destination_path=FILE_SAVE_PATH + file_info.get('name'))

                        if download:
                            logging.info(f"Fichier {file_id} téléchargé en mémoire. Taille: {len(download.getvalue())} bytes.")
                        else:
                            logging.error(f"Échec du téléchargement du fichier {file_id}.")

                else:
                    logging.info(f"  Changement sur fichier/dossier ID: {file_id} (supprimé ou inaccessible).")

            if new_start_page_token:
                save_startpagetoken(resource_id, new_start_page_token, local) # Sauvegarde le token pour le prochain cycle.
                logging.info(f"startPageToken mis à jour vers : {new_start_page_token} pour ressource {resource_id}")
        else:
            logging.info("Aucun changement significatif détecté par changes.list() malgré la notification du webhook.")

    except Exception as e:
        # En cas d'erreur lors du traitement (par exemple, un problème avec l'API Drive ou Firestore),
        # il est important de logguer l'erreur. Cependant, il est généralement recommandé de quand même
        # renvoyer un statut 200 OK à Google pour éviter qu'il ne considère le webhook comme défaillant.
        logging.error(f"Erreur lors du traitement du webhook pour ressource {resource_id}: {e}", exc_info=True)
        response_data = {"status": "processed_with_error", "error": str(e)}
    finally:
        logging.info(f"Fin du traitement asynchrone pour la ressource : {resource_id}")



@app.route('/webhook', methods=['POST'])
def webhook():

    # --- 1. Confirmer la réception immédiatement (Réponse 200 OK) ---
    # Il est essentiel de répondre rapidement pour éviter que Google ne ré-essaie ou ne désactive le webhook.
    # On prépare une réponse par défaut qui sera envoyée.
    response_data = {"status": "received", "message": "Processing in background"}
    status_code = 200 # Le statut HTTP par défaut est 200 OK.

    # --- Récupérer les en-têtes (informations clés de la notification) ---
    # Les informations cruciales sont dans les en-têtes HTTP de la requête POST, le corps est souvent vide.
    channel_id = request.headers.get('X-Goog-Channel-ID')     # L'ID du canal que vous avez créé.
    resource_id = request.headers.get('X-Goog-Resource-ID')   # L'ID de la ressource Drive surveillée (fichier ou Shared Drive).
    resource_state = request.headers.get('X-Goog-Resource-State') # L'état de la ressource (ex: 'change', 'sync', 'trash').
    channel_token = request.headers.get('X-Goog-Channel-Token') # Le token secret que vous avez fourni lors de la création.
    message_number = request.headers.get('X-Goog-Message-Number') # Numéro de message incrémental pour le canal.

    print(resource_id)
    
    logging.info(f"Webhook Headers: ChannelID={channel_id}, ResourceID={resource_id}, State={resource_state}, Token={channel_token}, MsgNum={message_number}")
    # Décoder le corps de la requête. Il est souvent vide ou contient des données non-JSON importantes pour certains types d'événements.
    logging.info(f"Webhook Body (usually empty): {request.data.decode('utf-8', errors='ignore')}")

    # --- 2. Vérifier l'authenticité ---
    # Cette étape est cruciale pour s'assurer que la notification provient bien de Google et non d'une source malveillante.
    if not os.environ.get('CHANNEL_TOKEN') or channel_token != os.environ.get('CHANNEL_TOKEN'):
        logging.error(f"Erreur de sécurité: X-Goog-Channel-Token incorrect. Attendu: '{os.environ.get('CHANNEL_TOKEN')}', Reçu: '{channel_token}'")
        response_data = {"error": "Unauthorized webhook token"}
        status_code = 403 # Retourne un statut 403 Forbidden si le token ne correspond pas.
        return jsonify(response_data), status_code

    # Les notifications de type 'sync' sont des pings de Google pour confirmer que le canal est actif.
    # Elles ne contiennent pas de changements réels et ne nécessitent pas d'interroger l'API Drive.
    if resource_state == 'sync':
        logging.info("Webhook de synchronisation/confirmation reçu. Pas de traitement des changements à ce stade.")
        return jsonify({"status": "sync_acknowledged"}), 200

    # --- Déclenchement de la fonction de traitement longue dans un thread séparé ---
    # Il est crucial de passer toutes les informations nécessaires à la fonction du thread.
    thread_args = (resource_id, resource_state, local)
    thread = threading.Thread(target=gdrive_sync_check, args=thread_args)
    thread.start() # Démarre le thread en arrière-plan

    logging.info(f"Requête webhook pour {resource_id} acceptée, traitement délégué à un thread.")
    return jsonify(response_data), status_code # Renvoie la réponse JSON avec le statut approprié.


if __name__ == '__main__':
    load_dotenv()

    FILE_SAVE_PATH = 'downloaded_files/' 

    try:
        from google.cloud import firestore
        firestore_client = firestore.Client() # Le client Firestore s'initialise avec les identifiants par défaut de Cloud Run.
        local = False
    except ImportError:
        USER_TO_IMPERSONATE = None
        LOCAL_TOKEN_DB_FILE = 'local_webhook_tokens.json'
        drive_service_receiver = None
        local = True

    if local:
        app.run(host="0.0.0.0", port=8080, debug=True)
    else:
        port = int(os.environ.get("PORT", 8080))
        app.run(host="0.0.0.0", port=port)

