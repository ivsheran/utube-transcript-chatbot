# drive.py

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from docx import Document
import io
import os
from config import DRIVE_FOLDER_ID

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
OAUTH_CREDENTIALS_FILE = "credentials/oauth_credentials.json"
OAUTH_TOKEN_FILE = "credentials/token.json"


def authenticate_drive():
    """
    Authenticate with Google Drive using OAuth 2.0.
    Opens browser on first run, uses saved token afterwards.
    
    :return: Google Drive service instance
    """
    creds = None

    # Load saved token if it exists
    if os.path.exists(OAUTH_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(OAUTH_TOKEN_FILE, SCOPES)

    # If no valid credentials, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                OAUTH_CREDENTIALS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save token for future use
        with open(OAUTH_TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return build("drive", "v3", credentials=creds)


def create_transcript_docx(transcript_text: str, video_url: str) -> io.BytesIO:
    """
    Create a .docx file in memory from the transcript text.
    
    :param transcript_text: Formatted transcript with timestamps
    :param video_url: YouTube video URL for the document title
    :return: BytesIO object containing the .docx file
    """
    doc = Document()
    doc.add_heading("YouTube Video Transcript", level=1)
    doc.add_paragraph(f"Source: {video_url}")
    doc.add_paragraph("")
    doc.add_paragraph(transcript_text)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


def upload_to_drive(docx_buffer: io.BytesIO, filename: str) -> str:
    """
    Upload a .docx file to Google Drive.
    
    :param docx_buffer: BytesIO object containing the .docx file
    :param filename: Name for the file in Google Drive
    :return: Shareable link to the uploaded file
    """
    service = authenticate_drive()

    file_metadata = {
        "name": filename,
        "parents": [DRIVE_FOLDER_ID],
        "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    }

    media = MediaIoBaseUpload(
        docx_buffer,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id, webViewLink"
    ).execute()

    return file.get("webViewLink")


def save_transcript_to_drive(transcript_text: str, video_url: str) -> str:
    """
    Full pipeline — create docx and upload to Google Drive.
    
    :param transcript_text: Formatted transcript with timestamps
    :param video_url: YouTube video URL
    :return: Shareable link to the uploaded file
    """
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"transcript_{timestamp}.docx"

    docx_buffer = create_transcript_docx(transcript_text, video_url)
    link = upload_to_drive(docx_buffer, filename)
    return link