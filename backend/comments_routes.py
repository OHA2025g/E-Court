"""Comments and @mentions on tracker entries."""
import re
from typing import Callable, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

MENTION_RE = re.compile(r"@([\w.+-]+@[\w.-]+\.\w+)")


class CommentIn(BaseModel):
    tracker: str
    entry_id: str
    body: str


def register_comments_routes(
    api, db, require_fully_authenticated, serialize_fn, now_utc_fn, notify_fn: Callable,
):
    @api.get("/comments")
    async def list_comments(
        tracker: str, entry_id: str,
        user: dict = Depends(require_fully_authenticated),
    ):
        items = await db.entry_comments.find({"tracker": tracker, "entry_id": entry_id}).sort("ts", 1).to_list(200)
        return serialize_fn(items)

    @api.post("/comments")
    async def add_comment(body: CommentIn, user: dict = Depends(require_fully_authenticated)):
        if user.get("role") == "Viewer":
            raise HTTPException(status_code=403, detail="Read-only")
        mentions = list(set(MENTION_RE.findall(body.body)))
        doc = {
            "tracker": body.tracker,
            "entry_id": body.entry_id,
            "body": body.body,
            "mentions": mentions,
            "author": user["email"],
            "ts": now_utc_fn(),
        }
        r = await db.entry_comments.insert_one(doc)
        if mentions:
            await notify_fn(
                mentions,
                f"Mention on {body.tracker} entry",
                f"{user['email']}: {body.body[:200]}",
                kind="info",
                link=f"/{body.tracker}",
            )
        return {"id": str(r.inserted_id)}
