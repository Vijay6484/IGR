#!/usr/bin/env python3
import os
import sys
import mimetypes

from dotenv import load_dotenv


def safe_print(*args):
    try:
        print("[UPLOAD]", *args, flush=True)
    except Exception:
        pass


def build_drive_service_from_env():
    """
    Uses the same env vars as 1.py for OAuth/service account.
    Recommended for personal accounts: GDRIVE_AUTH_MODE=oauth.
    """
    from googleapiclient.discovery import build

    scopes = ["https://www.googleapis.com/auth/drive"]
    auth_mode = os.environ.get("GDRIVE_AUTH_MODE", "oauth").strip().lower()

    if auth_mode == "service_account":
        from google.oauth2 import service_account

        sa_file = os.environ.get("GDRIVE_SERVICE_ACCOUNT_FILE", "").strip()
        if not sa_file:
            raise RuntimeError("GDRIVE_SERVICE_ACCOUNT_FILE is required for service_account auth")
        creds = service_account.Credentials.from_service_account_file(sa_file, scopes=scopes)
        return build("drive", "v3", credentials=creds, cache_discovery=False)

    if auth_mode == "oauth":
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        token_file = os.environ.get("GDRIVE_OAUTH_TOKEN_FILE", "token.json").strip() or "token.json"
        client_id = os.environ.get("GDRIVE_OAUTH_CLIENT_ID", "").strip()
        client_secret = os.environ.get("GDRIVE_OAUTH_CLIENT_SECRET", "").strip()
        secrets_file = os.environ.get("GDRIVE_OAUTH_CLIENT_SECRETS_FILE", "").strip()

        if client_id and client_secret:
            client_config = {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost"],
                }
            }
            flow_factory = lambda scopes: InstalledAppFlow.from_client_config(client_config, scopes)
        elif secrets_file:
            flow_factory = lambda scopes: InstalledAppFlow.from_client_secrets_file(secrets_file, scopes)
        else:
            raise RuntimeError("OAuth requires GDRIVE_OAUTH_CLIENT_ID+GDRIVE_OAUTH_CLIENT_SECRET or GDRIVE_OAUTH_CLIENT_SECRETS_FILE")

        creds = None
        if os.path.exists(token_file):
            try:
                creds = Credentials.from_authorized_user_file(token_file, scopes=scopes)
            except Exception:
                creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = flow_factory(scopes)
                creds = flow.run_local_server(port=0)
            with open(token_file, "w", encoding="utf-8") as f:
                f.write(creds.to_json())

        return build("drive", "v3", credentials=creds, cache_discovery=False)

    raise RuntimeError(f"Unknown GDRIVE_AUTH_MODE='{auth_mode}'")


def ensure_root_folder_id(service):
    """
    Use GDRIVE_ROOT_FOLDER_ID if set, else find/create GDRIVE_ROOT_FOLDER_NAME in My Drive root.
    """
    root_id = os.environ.get("GDRIVE_ROOT_FOLDER_ID", "").strip()
    if root_id:
        return root_id

    root_name = os.environ.get("GDRIVE_ROOT_FOLDER_NAME", "scraper_output").strip() or "scraper_output"
    escaped = root_name.replace("'", "\\'")
    q = (
        "mimeType='application/vnd.google-apps.folder' and "
        f"name='{escaped}' and "
        "'root' in parents and trashed=false"
    )
    resp = service.files().list(q=q, fields="files(id,name)", pageSize=10, supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
    files = resp.get("files", [])
    if files:
        return files[0]["id"]

    created = service.files().create(
        body={"name": root_name, "mimeType": "application/vnd.google-apps.folder", "parents": ["root"]},
        fields="id",
        supportsAllDrives=True,
    ).execute()
    return created["id"]


def main():
    load_dotenv()

    local_root = os.environ.get("LOCAL_SCRAPER_OUTPUT_DIR", "scraper_output").strip() or "scraper_output"
    local_root = os.path.abspath(local_root)
    if not os.path.isdir(local_root):
        safe_print(f"Local folder not found: {local_root}")
        sys.exit(1)

    safe_print("Local root:", local_root)

    service = build_drive_service_from_env()
    root_folder_id = ensure_root_folder_id(service)

    from drive_storage import DriveStorage

    storage = DriveStorage(service=service, root_folder_id=root_folder_id, safe_print=safe_print, supports_all_drives=True)

    uploaded = 0
    skipped = 0
    failed = 0

    for dirpath, _, filenames in os.walk(local_root):
        for fn in filenames:
            local_path = os.path.join(dirpath, fn)
            try:
                rel = os.path.relpath(local_path, local_root)
                rel_parts = rel.split(os.sep)
                path_parts = rel_parts[:-1]
                filename = rel_parts[-1]

                # Read file and upload (overwrite if same name exists)
                with open(local_path, "rb") as f:
                    data = f.read()

                mime = mimetypes.guess_type(local_path)[0] or "application/octet-stream"
                storage.upsert_bytes(path_parts, filename, data, mime=mime)
                uploaded += 1

                if uploaded % 50 == 0:
                    safe_print(f"Uploaded {uploaded} files so far...")
            except Exception as e:
                failed += 1
                safe_print(f"FAILED: {local_path} -> {e}")

    safe_print(f"Done. uploaded={uploaded} skipped={skipped} failed={failed}")


if __name__ == "__main__":
    main()

