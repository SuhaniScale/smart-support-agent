from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from pathlib import Path
from io import BytesIO
from docx import Document

TOKEN_FILE = "../token.json"


def get_credentials():
    return Credentials.from_authorized_user_file(TOKEN_FILE)


def get_drive_doc(keyword: str) -> str:
    """Searches Drive for a DOCX document whose name contains the keyword and returns its text."""

    creds = get_credentials()
    service = build("drive", "v3", credentials=creds)

    results = service.files().list(
        q=f"name contains '{keyword}'",
        fields="files(id, name, mimeType)",
    ).execute()

    files = results.get("files", [])

    if not files:
        return f"No document found matching '{keyword}'."

    file = files[0]

    print("Found file:", file)

    content = service.files().get_media(
        fileId=file["id"]
    ).execute()

    # Read DOCX content
    document = Document(BytesIO(content))

    text = []

    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            text.append(paragraph.text)

    return "\n".join(text)


if __name__ == "__main__":
    result = get_drive_doc("Runbook")
    print("\n--- RUNBOOK CONTENT ---\n")
    print(result)