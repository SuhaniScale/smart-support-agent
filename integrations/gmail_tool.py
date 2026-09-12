import base64
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

TOKEN_FILE = "../token.json"
CLIENT_SECRET_FILE = "../oauth_client_secret.json"

def get_credentials():
    return Credentials.from_authorized_user_file(TOKEN_FILE)


def draft_gmail(to_email: str, subject: str, body: str) -> str:
    """Creates a Gmail draft (never sends it) and returns the draft ID."""
    creds = get_credentials()
    service = build("gmail", "v1", credentials=creds)

    message = MIMEText(body)
    message["to"] = to_email
    message["subject"] = subject

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

    draft = service.users().drafts().create(
        userId="me",
        body={"message": {"raw": raw_message}},
    ).execute()

    return draft["id"]


if __name__ == "__main__":
    draft_id = draft_gmail(
        to_email="mobile-product-lead@example.com",
        subject="[EPC Platform] Escalation: Photo Upload Failures on Android",
        body="A cluster of 4 tickets reporting Android photo upload crashes has been escalated. Impact score: 78/100 (High).",
    )
    print(f"Draft created successfully. Draft ID: {draft_id}")
