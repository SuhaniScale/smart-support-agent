from mcp.server.fastmcp import FastMCP

from drive_tool import get_drive_doc
from gmail_tool import draft_gmail
from discord_notifier import send_discord_alert

mcp = FastMCP("EPC Enterprise Tools")


@mcp.tool()
def get_drive_document(keyword: str) -> str:
    """
    Search Google Drive for a reference document whose name matches
    the keyword and return its full text content.
    """
    return get_drive_doc(keyword)


@mcp.tool()
def draft_gmail_notification(
    to_email: str,
    subject: str,
    body: str,
) -> str:
    """
    Create a draft (unsent) Gmail notification.
    Returns the draft ID.
    """
    return draft_gmail(
        to_email,
        subject,
        body,
    )


@mcp.tool()
def send_discord_notification(
    title: str,
    message: str,
) -> str:
    """
    Send an alert to the configured Discord channel.
    Returns 'sent' or 'failed'.
    """
    success = send_discord_alert(
        title,
        message,
    )

    return "sent" if success else "failed"


if __name__ == "__main__":
    mcp.run()