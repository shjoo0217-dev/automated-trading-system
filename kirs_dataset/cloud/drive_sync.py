"""Optional private Drive archive sync using a separately granted offline OAuth.

GDRIVE_OAUTH_JSON must contain client_id, client_secret, refresh_token.
The connected ChatGPT Drive token is intentionally never exported to Actions.
"""
import argparse
import json
import os
from pathlib import Path
import requests


def main():
    p = argparse.ArgumentParser()
    p.add_argument("archive", type=Path)
    p.add_argument("--folder-id", required=True)
    a = p.parse_args()
    if not os.getenv("GDRIVE_OAUTH_JSON"):
        print("Drive sync NOT performed: offline OAuth secret missing")
        return
    secret = json.loads(os.environ["GDRIVE_OAUTH_JSON"])
    token_response = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": secret["client_id"], "client_secret": secret["client_secret"],
        "refresh_token": secret["refresh_token"], "grant_type": "refresh_token"}, timeout=30)
    if token_response.status_code != 200:
        raise RuntimeError("Drive OAuth refresh failed; response redacted")
    s = requests.Session()
    s.headers["Authorization"] = "Bearer " + token_response.json()["access_token"]
    meta = s.get(f"https://www.googleapis.com/drive/v3/files/{a.folder_id}",
        params={"fields": "id,mimeType,capabilities(canAddChildren)", "supportsAllDrives": "true"}, timeout=30)
    if meta.status_code != 200 or not meta.json().get("capabilities", {}).get("canAddChildren"):
        raise RuntimeError("Drive destination not writable")
    # Versioned names are immutable: refuse duplicates rather than replace latest bytes.
    q = f"'{a.folder_id}' in parents and name = '{a.archive.name}' and trashed = false"
    lookup = s.get("https://www.googleapis.com/drive/v3/files", params={"q": q, "fields": "files(id,name)", "spaces": "drive"}, timeout=30)
    if lookup.status_code != 200: raise RuntimeError("Drive duplicate lookup failed")
    if lookup.json().get("files"):
        print("Version already on Drive; no overwrite")
        return
    with a.archive.open("rb") as f:
        response = s.post("https://www.googleapis.com/upload/drive/v3/files", params={"uploadType": "multipart", "fields": "id,name,webViewLink,md5Checksum"},
            files={"metadata": (None, json.dumps({"name": a.archive.name, "parents": [a.folder_id]}), "application/json"),
                   "file": (a.archive.name, f, "application/zip")}, timeout=120)
    if response.status_code not in {200, 201}: raise RuntimeError("Drive upload failed; response redacted")
    item = response.json()
    check = s.get(f"https://www.googleapis.com/drive/v3/files/{item['id']}", params={"fields": "id,name,md5Checksum,webViewLink,size"}, timeout=30)
    import hashlib
    if check.status_code != 200 or check.json().get("md5Checksum") != hashlib.md5(a.archive.read_bytes()).hexdigest():
        raise RuntimeError("Drive readback checksum failed")
    print(json.dumps(check.json()))


if __name__ == "__main__": main()
