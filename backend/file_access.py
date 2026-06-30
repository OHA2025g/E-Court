"""Authorization checks for uploaded files."""
from task_permissions import can_access_task


async def user_can_access_file(db, user: dict, rec: dict) -> bool:
    if not rec:
        return False
    if user.get("role") == "Admin":
        return True
    if rec.get("uploaded_by") == user.get("email"):
        return True
    uid = user.get("id")
    storage_path = rec.get("storage_path") or ""
    if uid and f"/uploads/{uid}/" in storage_path:
        return True
    file_id = rec.get("id")
    if not file_id:
        return False
    evidence = await db.tm_evidence.find_one({"file_id": file_id})
    if evidence and evidence.get("task_id"):
        task = await db.tm_tasks.find_one({"id": evidence["task_id"]})
        if task and await can_access_task(db, user, task):
            return True
    return False
