"""Server-side cache for bulk upload dry-run previews."""
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

PREVIEW_TTL_MINUTES = 30


async def save_bulk_preview(
    db,
    user_id: str,
    tracker: str,
    reporting_period: str,
    filename: str,
    raw: bytes,
) -> str:
    token = secrets.token_urlsafe(24)
    now = datetime.now(timezone.utc)
    await db.bulk_previews.delete_many({
        "user_id": user_id,
        "tracker": tracker,
        "reporting_period": reporting_period,
    })
    await db.bulk_previews.insert_one({
        "token": token,
        "user_id": user_id,
        "tracker": tracker,
        "reporting_period": reporting_period,
        "filename": filename,
        "raw": raw,
        "created_at": now,
        "expires_at": now + timedelta(minutes=PREVIEW_TTL_MINUTES),
    })
    return token


async def consume_bulk_preview(
    db,
    token: str,
    user_id: str,
    tracker: str,
    reporting_period: str,
) -> tuple[bytes, str]:
    doc = await db.bulk_previews.find_one({
        "token": token,
        "user_id": user_id,
        "tracker": tracker,
        "reporting_period": reporting_period,
    })
    if not doc:
        raise HTTPException(status_code=400, detail="Invalid or expired preview token")
    expires = doc.get("expires_at")
    if expires and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires and expires < datetime.now(timezone.utc):
        await db.bulk_previews.delete_one({"token": token})
        raise HTTPException(status_code=400, detail="Preview expired — upload the file again")
    await db.bulk_previews.delete_one({"token": token})
    return doc["raw"], doc.get("filename") or "upload.xlsx"
