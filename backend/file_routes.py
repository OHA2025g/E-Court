"""File upload and download routes (object storage or local fallback)."""
import logging
import os
import uuid as _uuid
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import requests
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile

from file_access import user_can_access_file
from security import validate_upload_bytes
from task_permissions import resolve_task_role

logger = logging.getLogger("pmis")

STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXT = {"pdf", "png", "jpg", "jpeg", "webp", "doc", "docx", "xls", "xlsx", "csv", "txt"}
LOCAL_STORAGE_ROOT = Path(__file__).resolve().parent / "local_storage"
INLINE_EXTENSIONS = frozenset({"png", "jpg", "jpeg", "webp"})


def register_file_routes(
    api: APIRouter,
    db,
    require_fully_authenticated,
    serialize_fn,
    now_utc_fn,
    app_name: str,
    emergent_llm_key: Optional[str],
):
    _storage_key: dict = {"value": None}
    use_local = not emergent_llm_key

    def _init_storage() -> Optional[str]:
        if use_local:
            LOCAL_STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
            return "local"
        if _storage_key["value"]:
            return _storage_key["value"]
        try:
            r = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": emergent_llm_key}, timeout=30)
            r.raise_for_status()
            _storage_key["value"] = r.json()["storage_key"]
            return _storage_key["value"]
        except Exception as e:
            logger.error("Storage init failed: %s", e)
            return None

    def _local_path(storage_path: str) -> Path:
        return LOCAL_STORAGE_ROOT / storage_path

    def _put_object(path: str, data: bytes, content_type: str) -> dict:
        key = _init_storage()
        if not key:
            raise HTTPException(status_code=503, detail="Object storage unavailable")
        if key == "local":
            full = _local_path(path)
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_bytes(data)
            return {"path": path, "size": len(data)}
        r = requests.put(f"{STORAGE_URL}/objects/{path}",
                         headers={"X-Storage-Key": key, "Content-Type": content_type},
                         data=data, timeout=120)
        if r.status_code == 403:
            _storage_key["value"] = None
            key = _init_storage()
            r = requests.put(f"{STORAGE_URL}/objects/{path}",
                             headers={"X-Storage-Key": key, "Content-Type": content_type},
                             data=data, timeout=120)
        r.raise_for_status()
        return r.json()

    def _get_object(path: str):
        key = _init_storage()
        if not key:
            raise HTTPException(status_code=503, detail="Object storage unavailable")
        if key == "local":
            full = _local_path(path)
            if not full.is_file():
                raise HTTPException(status_code=404, detail="File not found in storage")
            return full.read_bytes(), "application/octet-stream"
        r = requests.get(f"{STORAGE_URL}/objects/{path}",
                         headers={"X-Storage-Key": key}, timeout=60)
        if r.status_code == 403:
            _storage_key["value"] = None
            key = _init_storage()
            r = requests.get(f"{STORAGE_URL}/objects/{path}",
                             headers={"X-Storage-Key": key}, timeout=60)
        r.raise_for_status()
        return r.content, r.headers.get("Content-Type", "application/octet-stream")

    def init_storage_on_startup() -> bool:
        ok = bool(_init_storage())
        if ok and use_local:
            logger.info("File uploads using local storage at %s", LOCAL_STORAGE_ROOT)
        return ok

    @api.post("/files/upload")
    async def upload_file(file: UploadFile = File(...), user: dict = Depends(require_fully_authenticated)):
        if user.get("role") == "Viewer" and resolve_task_role(user) == "auditor":
            raise HTTPException(status_code=403, detail="Read-only role")
        raw = await file.read()
        if len(raw) > MAX_FILE_BYTES:
            raise HTTPException(status_code=413, detail="File exceeds 10 MB limit")
        name = file.filename or "upload.bin"
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else "bin"
        if ext not in ALLOWED_EXT:
            raise HTTPException(status_code=400, detail=f"File type '.{ext}' not allowed")
        validate_upload_bytes(raw, ext)
        path = f"{app_name}/uploads/{user['id']}/{_uuid.uuid4()}.{ext}"
        result = _put_object(path, raw, file.content_type or "application/octet-stream")
        file_id = str(_uuid.uuid4())
        doc = {
            "id": file_id, "storage_path": result["path"],
            "original_filename": name, "content_type": file.content_type,
            "size": result.get("size", len(raw)), "is_deleted": False,
            "uploaded_by": user["email"], "created_at": now_utc_fn(),
            "storage_backend": "local" if use_local else "emergent",
        }
        await db.files.insert_one(doc)
        return {"id": file_id, "filename": name, "size": doc["size"], "content_type": doc["content_type"]}

    @api.get("/files/{file_id}")
    async def download_file(file_id: str, user: dict = Depends(require_fully_authenticated)):
        rec = await db.files.find_one({"id": file_id, "is_deleted": False})
        if not rec:
            raise HTTPException(status_code=404, detail="File not found")
        if not await user_can_access_file(db, user, rec):
            raise HTTPException(status_code=403, detail="Not authorized for this file")
        data, ct = _get_object(rec["storage_path"])
        safe_name = quote(rec.get("original_filename") or "download", safe="")
        media_type = rec.get("content_type") or ct
        ext = (rec.get("original_filename") or "").rsplit(".", 1)[-1].lower() if "." in (rec.get("original_filename") or "") else ""
        disposition = "inline" if ext in INLINE_EXTENSIONS or (media_type or "").startswith("image/") else "attachment"
        return Response(
            content=data,
            media_type=media_type,
            headers={"Content-Disposition": f'{disposition}; filename="{safe_name}"; filename*=UTF-8\'\'{safe_name}'},
        )

    @api.get("/files/{file_id}/meta")
    async def file_meta(file_id: str, user: dict = Depends(require_fully_authenticated)):
        rec = await db.files.find_one({"id": file_id, "is_deleted": False}, {"_id": 0})
        if not rec:
            raise HTTPException(status_code=404, detail="File not found")
        if not await user_can_access_file(db, user, rec):
            raise HTTPException(status_code=403, detail="Not authorized for this file")
        return serialize_fn(rec)

    return init_storage_on_startup
