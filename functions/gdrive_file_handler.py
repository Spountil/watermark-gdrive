import logging
import io
import json
import os
import time
from ast import literal_eval
import firebase_admin
from firebase_admin import firestore
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from functions.watermark import Watermark
from functions.webhook import get_drive_service
from functions.gdrive_token import load_startpagetoken, save_startpagetoken

try:
    firebase_admin.initialize_app()
except ValueError:
    None

db = firestore.client()


def download_file(drive_service, file_id, destination_path=None, expected_file_size=None) -> bytes:
    """
    Download the content of a file from Google Drive.
    """
    try:
        request = drive_service.files().get_media(fileId=file_id)
        logging.info(request)
        file = io.BytesIO()
        downloader = MediaIoBaseDownload(file, request)
        done = False
        bytes_downloaded_total = 0 
        logging.info(f"File object created for {file_id}. Initial size: {file.tell()} bytes.")
        
        while not done:
            status, done = downloader.next_chunk()
            if status:
                logging.info(f"Downloaded progress for {file_id}: {int(status.progress() * 100)}% - Bytes received: {file.tell()} / {status.total_size}")
                bytes_downloaded_total = file.tell() 
            else:
                logging.warning(f"Status is None during download loop for {file_id}. Done: {done}")

        logging.info(f"Download completed for {file_id}. Total bytes written to buffer: {bytes_downloaded_total}")

        file.seek(0)
        file_content = file.read()

        if destination_path:
            if not os.path.exists(os.path.dirname(destination_path)):
                logging.info(f"Creating the directory for {destination_path}.")
                os.makedirs(os.path.dirname(destination_path))
                
            with open(destination_path, 'wb') as f:
                f.write(file_content)
            logging.info(f"File {file_id} downloaded and saved at: {destination_path}")


        logging.info(f"File {file_id} downloaded. Final size: {len(file_content)} bytes.")

        if expected_file_size and len(file_content) != expected_file_size:
            logging.error(f"CAREFUL: The downloaded file size ({len(file_content)} bytes) does NOT match the expected size ({expected_file_size} bytes) for {file_id}!")

        return file_content
        
    except Exception as e:
        logging.error(f"Error when downloading file {file_id} from Google Drive: {e}", exc_info=True)
        return None
    

def upload_file(drive_service, new_file_name, local_file_path, new_mime_type, parent_folder_id=None) -> dict:
    """
    Upload a file to Google Drive.
    """

    try:
        file_metadata = {
            'name': new_file_name,
            'parents': [parent_folder_id],
        }

        media_body = MediaFileUpload(local_file_path, new_mime_type, resumable=True)

        new_file = drive_service.files().create(
            body=file_metadata,
            media_body=media_body,
            fields='id,name,mimeType,size,parents,webViewLink',
            supportsAllDrives=True
        ).execute()

        logging.info(f"New file successfully created: '{new_file.get('name')}' (ID: {new_file.get('id')}). Size: {new_file.get('size')} bytes.")
        logging.info(f"URL of the new file: {new_file.get('webViewLink')}")
        return new_file
    
    except Exception as e:
        logging.error(f"Error when creating the file '{new_file_name}' on Google Drive : {e}", exc_info=True)
        return None
    

def gdrive_file_handler(resource_id, resource_state, FILE_SAVE_PATH, message_number):
    """
    Handle the asynchronous processing of Google Drive changes, and apply watermarks to images if criterias are met.
    """

    start = time.time()
    
    logging.info(f"Beginning asynchronous processing for resource: {resource_id}, state: {resource_state}")

    drive_service = get_drive_service()

    last_token = load_startpagetoken(resource_id)

    if not last_token:
        logging.warning(f"No previous startPageToken found for resource {resource_id}. Attempting to retrieve the current token.")
        start_page_token_response = drive_service.changes().getStartPageToken(supportsAllDrives=True).execute()
        last_token = start_page_token_response.get('startPageToken')
        save_startpagetoken(resource_id, last_token) # Sauvegarde ce token initial pour les futures exécutions.
        logging.info(f"Initial startPageToken retrieved and saved for {resource_id}: {last_token}")
    
    logging.info(f"Recovering changes from token: {last_token} for resource {resource_id}")
        
    # Check if the resource_id is a Shared Drive ID.
    # Shared Drive IDs are typically 33 characters long.
    is_shared_drive_resource = len(resource_id) == 33 

    # Call the `changes().list()` method to get the actual list of changes.
    results = drive_service.changes().list(
        pageToken=last_token,
        supportsAllDrives=True,
        includeRemoved=True,
        driveId=resource_id if is_shared_drive_resource else None, 
        fields="nextPageToken,newStartPageToken,changes(fileId,file(name,parents,mimeType,trashed,shared,size))"
    ).execute()

    changes = results.get('changes', [])
    new_start_page_token = results.get('newStartPageToken')

    if last_token == new_start_page_token:
        logging.info(f"No new changes detected for resource {resource_id} since the last token {last_token}.")
        return

    if new_start_page_token:
        save_startpagetoken(resource_id, new_start_page_token)
        logging.info(f"startPageToken updated to : {new_start_page_token} for resource {resource_id}")

    try:

        if changes:

            file_ids = db.collection("file_treated").document("file_ids").get().to_dict()

            if file_ids is None or file_ids == {}:
                logging.error(f"Error loading credentials from Firestore - {file_ids}")
                file_ids = []
            else:
                file_ids = file_ids.get('file_ids')
                
            logging.info(f"Number of changes detected : {len(changes)}")

            for change in changes:
                file_id = change.get('fileId')
                file_info = change.get('file')

                try:
                    file_info.get('trashed')
                except:
                    print(f"File {file_id} does not have a 'trashed' attribute. File info: {file_info}.")
                    continue
                
                if (file_info.get('trashed')) or (not 'image/' in file_info.get('mimeType')):
                    logging.info(f"Changed ignored for the file ID: {file_id} (deleted or non-image).")
                    continue

                nb_file_downloaded = 0

                if file_info:
                    parents = file_info.get('parents', [])
                    file_size = int(file_info.get('size', 0))

                    # Check if the file is in the watched folder by comparing its parents with the FILE_ID environment variable.
                    if os.getenv('FILE_ID') in parents:
                        logging.info(f"File {file_info.get('name')} in a watched folder.")
                        is_param = False

                        if file_id in file_ids:
                            logging.info(f"Changes already handled for file ID: {file_id}. Ignored.")
                            continue
                        else:
                            file_ids.append(file_id)
                            logging.info(f"Handling changes for file ID: {file_id}")

                            # Use a list of the previously processed file IDs to avoid reprocessing, especially in case of multiple changes.
                            file_ids = file_ids[-50:]  # Limite the size of the file_ids list to the last 50 processed files.

                            db.collection("file_treated").document("file_ids").set({'file_ids': file_ids})

                    elif os.getenv('SETTING_FILE_ID') in parents:
                        logging.info(f"File {file_info.get('name')} is a settings file.")
                        is_param = True

                        if file_info.get('name').endswith('.json'):
                            folder = '/files/settings/'
                        else:
                            folder = '/files/logo/'

                        download_file(drive_service, file_id, destination_path=os.getcwd() + folder + file_info.get('name'), expected_file_size=file_size)
                        continue
                    else:
                        logging.info(f"File {file_info.get('name')} not in a watched folder. Ignored.")
                        continue

                    logging.info(f"Changes in file/folder ID: {file_id}, Name: {file_info.get('name')}, Parents: {parents}, State: {'Deleted' if file_info.get('trashed') else 'Active'}, Size: {file_size} bytes")

                    path_file = FILE_SAVE_PATH + file_info.get('name')

                    # Check if settings and logo files exist, if not, download them from Google Drive.
                    path_params = [os.getcwd() + '/files/settings/settings.json',
                                    os.getcwd() + '/files/logo/logo.png']

                    for param in path_params:
                        if not os.path.exists(param):
                            logging.error(f"File {param} not found. Starting the download of the file {param}.")

                            if param.endswith('settings.json'):
                                mime_type = 'application/json'
                                name = 'settings.json'
                            else:
                                mime_type = 'image/png'
                                name = 'logo.png'
                                        
                            param_file = drive_service.files().list(
                                q=f"mimeType='{mime_type}'",
                                spaces="drive",
                                fields="nextPageToken, files(id, name, size)",
                                pageToken=None,
                            ).execute()

                            for file in param_file.get('files', []):
                                if file.get('name') == name:
                                    param_file_id = file.get('id')
                                    param_file_size = file.get('size')
                                    download_file(drive_service, param_file_id, destination_path=param, expected_file_size=param_file_size)
                                    break

                    download = download_file(drive_service, file_id, destination_path=path_file, expected_file_size=file_size)

                    if download:
                        logging.info(f"File {file_id} downloaded in memory. Size: {len(download)} bytes.")

                        nb_file_downloaded += 1
                    else:
                        logging.error(f"Downloading of the file {file_id} failed.")

                else:
                    logging.info(f"Changes in the folder/file ID: {file_id} (deleted or not found).")

            nb_file_to_mrkd = 0

            for file in os.listdir(FILE_SAVE_PATH):
                if file.startswith('.') or file.endswith('_mrkd.png'):
                    continue

                logging.info(f"Adding the watermark on the file {file}...")

                with open(os.getcwd() + '/files/settings/settings.json', 'r') as f:
                    settings = json.load(f)

                path_file = FILE_SAVE_PATH + file

                wtmrk = Watermark(
                    path=path_file,
                    path_logo=os.getenv('LOGO_PATH'),
                    colors=literal_eval(settings['colors']), 
                    opacity=settings['opacity'] 
                    )

                # Apply the watermark to the image.
                # Note: Make sure the image is in a compatible format (e.g. HEIC, PNG, etc.) for the PIL package.
                new_file_path = wtmrk.img_watermark()

                logging.info(f"Watermark applied ot the file {file_info.get('name')}.")

                os.remove(path_file)  # Delete the file in the folder
                logging.info(f"Original file {file} deleted after watermarking.")

                nb_file_to_mrkd += 1

            nb_file_uploaded = 0

            for file_mrkd in os.listdir(FILE_SAVE_PATH):
                if file_mrkd.startswith('.') or not file_mrkd.endswith('_mrkd.png'):
                    continue

                path_file = FILE_SAVE_PATH + file_mrkd

                logging.info(f"Upload in folder id {os.getenv('RESULT_FILE_ID')}.")
                reply = upload_file(
                    drive_service,
                    new_file_name=path_file.split('/')[-1],
                    local_file_path=path_file,
                    new_mime_type='image/png',
                    parent_folder_id=os.getenv('RESULT_FILE_ID')
                    )

                os.remove(path_file)  # Delete the file in the folder
                logging.info(f"Watermarked file {file_mrkd} deleted after upload.")

                nb_file_uploaded += 1

            if nb_file_downloaded or nb_file_to_mrkd or nb_file_uploaded:
                logging.info(f"Processing summary for resource {resource_id}: Downloaded: {nb_file_downloaded}, Watermarked: {nb_file_to_mrkd}, Uploaded: {nb_file_uploaded}")
                end = time.time()
                timing = end - start
                db.collection("log_time").document(resource_id).set({'Processing time': timing, 'Number of files downloaded': nb_file_downloaded, 'Number of files watermarked': nb_file_to_mrkd, 'Number of files uploaded': nb_file_uploaded}, merge=True)
                
        else:
            logging.info("No significant changes detected by changes.list() despite notification from the webhook.")

    except Exception as e:
        logging.error(f"Error while handling the webhook for resource {resource_id}: {e}", exc_info=True)
        response_data = {"status": "processed_with_error", "error": str(e)}
    finally:
        logging.info(f"Thread for resource {resource_id} completed.")