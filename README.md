# Watermark from Google Drive

## Objective

Add a watermark to one or multiple images added to a Google Drive folder, and return the new images to a result folder

## Project Idea

For a request received to automate the addition of a watermark to a few images, I decided to automate it on a Google Drive folder to be able to monitor, and handle the updates in an easier manner. <p>
The idea was mainly to learn and understand how to work with APIs, HTTP requests, and everything that is needed to handle the communication for an online product (here, Google Drive and Google Cloud Services).

## Tools Used

- **Google Drive**: One folder to add the images, and another for the result.
- **Google Run**: To run the server that will listen to the Google Drive's webhook (POST) and launch the subscription to the webhook when a GET request with a specific key is sent.
- **Google Schedule**: Schedule a GET call to the Cloud Run instance with a key to trigger the subscription to the webhook every 12 hours.
- **Google Storage**: To store the different file needed for the settings, and the temporary files.
- **Google Firestore**: To store the information that needs to be accessed and updated quickly

<br/>

![Image](/watermark-gdrive/watermark-gdrive.drawio.png)


