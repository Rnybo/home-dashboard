"""
Google Photos OAuth2 login script.
Kør dette script én gang på din pc for at generere token.json.
Kopiér derefter token.json og credentials.json til tabletten.

Forudsætninger:
1. Gå til https://console.cloud.google.com/apis/library
2. Søg efter "Photos Library API" og aktiver den
3. Gå til Credentials → Create Credentials → OAuth client ID
4. Vælg "Desktop app" som application type
5. Download JSON-filen og gem den som credentials.json i dette projekt
"""

import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ['https://www.googleapis.com/auth/photoslibrary.readonly']
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token_photos.json'

def login():
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            print("Token refreshed successfully.")
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"ERROR: {CREDENTIALS_FILE} not found!")
                print("Download it from Google Cloud Console → Credentials → your OAuth client → Download JSON")
                print("Save it as credentials.json in the project root.")
                return
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            print("Login successful!")

        with open(TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())
        print(f"Token saved to {TOKEN_FILE}")
        print(f"Copy {TOKEN_FILE} to your tablet at the same path.")
    else:
        print("Already logged in and token is valid.")

    # Quick test — list first 5 albums
    import requests
    headers = {'Authorization': f'Bearer {creds.token}'}
    r = requests.get(
        'https://photoslibrary.googleapis.com/v1/albums',
        headers=headers,
        params={'pageSize': 5}
    )
    if r.status_code == 200:
        albums = r.json().get('albums', [])
        print(f"\nFound {len(albums)} albums (first 5):")
        for a in albums:
            print(f"  - {a.get('title', '(untitled)')} ({a.get('mediaItemsCount', '?')} items)")
    else:
        print(f"API test failed: {r.status_code} {r.text[:200]}")

if __name__ == '__main__':
    login()
