
"""
==========================================================
Google OAuth Authorization Script
----------------------------------------------------------
For:
- GitHub Codespaces
- Google OAuth Web Application Client

Purpose:
- Google OAuth authorization
- Drive readonly permission
- Gmail compose permission
- Receive OAuth callback
- Save token.json
==========================================================
"""

from pathlib import Path
from flask import Flask, request
from google_auth_oauthlib.flow import Flow
import traceback
import os

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# ==========================================================
# Paths
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent

CLIENT_SECRET_FILE = (BASE_DIR / "../oauth_client_secret.json").resolve()
TOKEN_FILE = (BASE_DIR / "../token.json").resolve()


# ==========================================================
# OAuth Scopes
# ==========================================================

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]


# ==========================================================
# Codespaces Configuration
# ==========================================================

HOST = "0.0.0.0"
PORT = 8085

REDIRECT_URI = (
    "https://vigilant-engine-wvg5xp6g9p96hv459-8085"
    ".app.github.dev/oauth2callback"
)


# ==========================================================
# Flask
# ==========================================================

app = Flask(__name__)

flow = None


# ==========================================================
# Home Route
# ==========================================================

@app.route("/")
def home():

    print()
    print("--------------------------------------------------")
    print("WARNING: Google returned to '/' instead of")
    print("'/oauth2callback'")
    print("--------------------------------------------------")
    print("Full URL received:")
    print(request.url)
    print("--------------------------------------------------")
    print()

    return """
    <html>
        <body>
            <h2>OAuth Callback Error</h2>

            <p>
                Google returned to the wrong URL.
            </p>

            <p>
                Expected:
                <br>
                <b>/oauth2callback</b>
            </p>

            <p>
                Check the Authorized Redirect URI
                in Google Cloud Console.
            </p>
        </body>
    </html>
    """, 400


# ==========================================================
# OAuth Callback
# ==========================================================

@app.route("/oauth2callback")
def oauth2callback():

    global flow

    print()
    print("=" * 60)
    print("GOOGLE OAUTH CALLBACK RECEIVED")
    print("=" * 60)

    print()
    print("Callback URL:")
    print(request.url)

    print()
    print("Query parameters:")
    print(dict(request.args))

    try:

        # --------------------------------------------------
        # Check for Google OAuth error
        # --------------------------------------------------

        if "error" in request.args:

            error = request.args.get("error")
            error_description = request.args.get(
                "error_description",
                "No description provided"
            )

            print()
            print("GOOGLE OAUTH ERROR")
            print("Error:", error)
            print("Description:", error_description)

            return f"""
            <html>
                <body>
                    <h2>Google OAuth Error ❌</h2>
                    <p><b>{error}</b></p>
                    <p>{error_description}</p>
                </body>
            </html>
            """, 400

        # --------------------------------------------------
        # Check authorization code
        # --------------------------------------------------

        if "code" not in request.args:

            print()
            print("ERROR: No authorization code received.")

            return """
            <html>
                <body>
                    <h2>No authorization code received ❌</h2>
                </body>
            </html>
            """, 400

        # --------------------------------------------------
        # Exchange authorization code for token
        # --------------------------------------------------

        print()
        print("Exchanging authorization code for tokens...")

        flow.fetch_token(
            authorization_response=request.url
        )

        creds = flow.credentials

        print()
        print("Token exchange successful.")

        # --------------------------------------------------
        # Save token
        # --------------------------------------------------

        with open(TOKEN_FILE, "w") as token_file:
            token_file.write(creds.to_json())

        print()
        print("=" * 60)
        print("AUTHORIZATION SUCCESSFUL")
        print("=" * 60)

        print()
        print("Token saved at:")
        print(TOKEN_FILE)

        print()
        print("Drive scope:")
        print("https://www.googleapis.com/auth/drive.readonly")

        print()
        print("Gmail scope:")
        print("https://www.googleapis.com/auth/gmail.compose")

        print()
        print("=" * 60)

        return """
        <html>
            <body>
                <h2>Authorization Successful ✅</h2>

                <p>
                    Google authorization completed successfully.
                </p>

                <p>
                    <b>token.json</b> has been created.
                </p>

                <p>
                    You can close this window.
                </p>
            </body>
        </html>
        """

    except Exception as e:

        print()
        print("=" * 60)
        print("TOKEN EXCHANGE FAILED")
        print("=" * 60)

        print()
        print("Error:")
        print(str(e))

        print()
        print("Full traceback:")
        traceback.print_exc()

        print()
        print("=" * 60)

        return f"""
        <html>
            <body>
                <h2>OAuth Token Exchange Failed ❌</h2>

                <p>
                    <b>Error:</b>
                </p>

                <pre>{str(e)}</pre>

                <p>
                    Check the Codespaces terminal for
                    the full error.
                </p>
            </body>
        </html>
        """, 500


# ==========================================================
# Authorization
# ==========================================================

def authorize():

    global flow

    print()
    print("=" * 60)
    print("GOOGLE OAUTH AUTHORIZATION")
    print("=" * 60)

    print()
    print("Client secret:")
    print(CLIENT_SECRET_FILE)

    print()
    print("Token file:")
    print(TOKEN_FILE)

    print()
    print("Redirect URI:")
    print(REDIRECT_URI)

    print()
    print("=" * 60)

    # ------------------------------------------------------
    # Create OAuth Flow
    # ------------------------------------------------------

    try:

        flow = Flow.from_client_secrets_file(
            str(CLIENT_SECRET_FILE),
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )

    except Exception as e:

        print()
        print("FAILED TO LOAD CLIENT SECRET")
        print(str(e))

        traceback.print_exc()

        return

    # ------------------------------------------------------
    # Generate authorization URL
    # ------------------------------------------------------

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent"
    )

    print()
    print("=" * 60)
    print("OPEN THIS URL")
    print("=" * 60)

    print()
    print(authorization_url)

    print()
    print("=" * 60)
    print("IMPORTANT")
    print("=" * 60)

    print()
    print("After clicking Allow, Google should return to:")
    print()
    print(REDIRECT_URI)

    print()
    print("Do NOT manually change the URL.")

    print()
    print("=" * 60)

    # ------------------------------------------------------
    # Start Flask
    # ------------------------------------------------------

    print()
    print(f"Starting OAuth callback server on port {PORT}...")
    print()

    app.run(
        host=HOST,
        port=PORT,
        debug=False
    )


# ==========================================================
# Main
# ==========================================================

if __name__ == "__main__":
    authorize()

