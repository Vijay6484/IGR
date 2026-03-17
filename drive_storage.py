import io
import json
import mimetypes
import os
import tempfile
from typing import Any, Iterable, Optional


class DriveStorage:
    """
    Simple Google Drive-backed storage.

    Uses an existing authenticated Drive API client (`service`) plus a root folder ID.
    Creates subfolders as needed and caches folder IDs.
    """

    def __init__(self, service, root_folder_id: str, safe_print=None, supports_all_drives: bool = True):
        self.service = service
        self.root_folder_id = root_folder_id
        self.safe_print = safe_print or (lambda *a, **k: None)
        self.supports_all_drives = supports_all_drives
        self._folder_cache: dict[tuple[str, str], str] = {}  # (parent_id, name) -> id

    def _drive_kwargs(self):
        return {"supportsAllDrives": bool(self.supports_all_drives)}

    def _list_kwargs(self):
        return {"supportsAllDrives": bool(self.supports_all_drives), "includeItemsFromAllDrives": bool(self.supports_all_drives)}

    @staticmethod
    def _escape_query(s: str) -> str:
        return (s or "").replace("'", "\\'")

    def _get_or_create_folder(self, parent_id: str, name: str) -> str:
        key = (parent_id, name)
        if key in self._folder_cache:
            return self._folder_cache[key]

        q = (
            "mimeType='application/vnd.google-apps.folder' and "
            f"name='{self._escape_query(name)}' and "
            f"'{parent_id}' in parents and trashed=false"
        )
        resp = self.service.files().list(q=q, fields="files(id,name)", pageSize=10, **self._list_kwargs()).execute()
        files = resp.get("files", [])
        if files:
            folder_id = files[0]["id"]
            self._folder_cache[key] = folder_id
            return folder_id

        body = {"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]}
        created = self.service.files().create(body=body, fields="id", **self._drive_kwargs()).execute()
        folder_id = created["id"]
        self._folder_cache[key] = folder_id
        return folder_id

    def ensure_path(self, path_parts: Iterable[str]) -> str:
        current = self.root_folder_id
        for part in path_parts:
            if part is None:
                continue
            part = str(part).strip()
            if not part:
                continue
            current = self._get_or_create_folder(current, part)
        return current

    def _find_file_id(self, parent_id: str, filename: str) -> Optional[str]:
        q = f"name='{self._escape_query(filename)}' and '{parent_id}' in parents and trashed=false"
        resp = self.service.files().list(q=q, fields="files(id,name)", pageSize=10, **self._list_kwargs()).execute()
        files = resp.get("files", [])
        return files[0]["id"] if files else None

    def upsert_bytes(self, path_parts: Iterable[str], filename: str, content: bytes, mime: Optional[str] = None) -> str:
        """
        Create or overwrite a file at Drive path (folder path_parts + filename).
        Returns file id.
        """
        from googleapiclient.http import MediaFileUpload

        folder_id = self.ensure_path(path_parts)
        mime = mime or (mimetypes.guess_type(filename)[0] if filename else None) or "application/octet-stream"

        # Use a temp file for upload (acceptable per requirements)
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp_path = tmp.name
                tmp.write(content)

            existing_id = self._find_file_id(folder_id, filename)
            media = MediaFileUpload(tmp_path, mimetype=mime, resumable=True)
            if existing_id:
                updated = self.service.files().update(fileId=existing_id, media_body=media, fields="id", **self._drive_kwargs()).execute()
                return updated["id"]
            created = self.service.files().create(
                body={"name": filename, "parents": [folder_id]},
                media_body=media,
                fields="id",
                **self._drive_kwargs(),
            ).execute()
            return created["id"]
        finally:
            if tmp_path:
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    def create_bytes(self, path_parts: Iterable[str], filename: str, content: bytes, mime: Optional[str] = None) -> str:
        """
        Always create a new file (even if same name exists). Returns file id.
        """
        from googleapiclient.http import MediaFileUpload

        folder_id = self.ensure_path(path_parts)
        mime = mime or (mimetypes.guess_type(filename)[0] if filename else None) or "application/octet-stream"

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp_path = tmp.name
                tmp.write(content)
            media = MediaFileUpload(tmp_path, mimetype=mime, resumable=True)
            created = self.service.files().create(
                body={"name": filename, "parents": [folder_id]},
                media_body=media,
                fields="id",
                **self._drive_kwargs(),
            ).execute()
            return created["id"]
        finally:
            if tmp_path:
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    def read_bytes(self, path_parts: Iterable[str], filename: str) -> Optional[bytes]:
        from googleapiclient.http import MediaIoBaseDownload

        folder_id = self.ensure_path(path_parts)
        file_id = self._find_file_id(folder_id, filename)
        if not file_id:
            return None

        request = self.service.files().get_media(fileId=file_id, **self._drive_kwargs())
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return fh.getvalue()

    def read_json(self, path_parts: Iterable[str], filename: str) -> Optional[Any]:
        data = self.read_bytes(path_parts, filename)
        if data is None:
            return None
        try:
            return json.loads(data.decode("utf-8"))
        except Exception:
            return None

    def write_json(self, path_parts: Iterable[str], filename: str, obj: Any) -> str:
        content = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
        return self.upsert_bytes(path_parts, filename, content, mime="application/json")

