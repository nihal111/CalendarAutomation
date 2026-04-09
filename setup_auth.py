#!/usr/bin/env python3
"""Interactive setup for Google Calendar OAuth credentials.

Instead of downloading a credentials.json file from Google Cloud Console,
this script lets you paste your client ID and client secret directly.
It then generates credentials.json and runs the OAuth flow to create token.pickle.

Steps to get your client ID and secret (works on mobile):
1. Go to https://console.cloud.google.com/apis/credentials
2. Create a project (or select an existing one)
3. Enable the Google Calendar API:
   https://console.cloud.google.com/apis/library/calendar-json.googleapis.com
4. Go to Credentials -> Create Credentials -> OAuth client ID
5. Application type: Desktop app
6. Copy the Client ID and Client Secret shown on screen
7. Run this script and paste them in
"""

import json
import os
import sys
from datetime import datetime

CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), "credentials.json")
TOKEN_PATH = os.path.join(os.path.dirname(__file__), "token.pickle")


def create_credentials_file():
    """Prompt for client ID/secret and write credentials.json."""
    if os.path.exists(CREDENTIALS_PATH):
        resp = input("credentials.json already exists. Overwrite? [y/N]: ").strip().lower()
        if resp != "y":
            print("Keeping existing credentials.json")
            return

    print("\n--- Google Calendar OAuth Setup ---")
    print("Paste your OAuth client ID and client secret from Google Cloud Console.\n")

    client_id = input("Client ID: ").strip()
    if not client_id:
        print("Error: Client ID cannot be empty.")
        sys.exit(1)

    client_secret = input("Client Secret: ").strip()
    if not client_secret:
        print("Error: Client Secret cannot be empty.")
        sys.exit(1)

    credentials = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "redirect_uris": ["http://localhost"],
        }
    }

    with open(CREDENTIALS_PATH, "w") as f:
        json.dump(credentials, f, indent=2)

    print(f"\nWrote {CREDENTIALS_PATH}")


def run_auth_flow():
    """Trigger gcsa's OAuth flow to generate token.pickle."""
    print("\nStarting OAuth flow — a browser window will open for Google sign-in...")
    print("(If you're on a remote machine, copy the URL it prints and open it on your phone.)\n")

    try:
        from gcsa.google_calendar import GoogleCalendar
        gc = GoogleCalendar(
            credentials_path=CREDENTIALS_PATH,
            token_path=TOKEN_PATH,
        )
        # Trigger auth by making a simple request
        list(gc.get_events(time_min=datetime(2020, 1, 1), time_max=datetime(2020, 1, 1, 0, 1)))
        print("\nAuth successful! token.pickle has been created.")
        print("You're all set to use CalendarAutomation.")
    except Exception as e:
        print(f"\nAuth flow error: {e}")
        print("Make sure you've enabled the Google Calendar API in your Google Cloud project.")
        sys.exit(1)


if __name__ == "__main__":
    create_credentials_file()
    run_auth_flow()
