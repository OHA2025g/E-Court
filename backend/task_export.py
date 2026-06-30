"""Task Management — CSV, Excel, and PDF export."""
import csv
import io

import xlsxwriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from task_service import list_tasks_query

TASK_COLUMNS = [
    "task_code",
    "title",
    "status_label",
    "priority",
    "module_name",
    "department_name",
    "project_name",
    "due_date",
    "sla_status",
    "owner_name",
    "team_lead_name",
    "progress_pct",
]

TASK_HEADERS = [
    "Task Code",
    "Title",
    "Status",
    "Priority",
    "Module",
    "Department",
    "Project",
    "Due Date",
    "SLA Status",
    "Owner",
    "Team Lead",
    "Progress %",
]


def _row_from_task(task: dict) -> dict:
    due = task.get("due_date")
    due_str = str(due)[:10] if due else ""
    return {
        "task_code": task.get("task_code") or "",
        "title": task.get("title") or "",
        "status_label": task.get("status_label") or task.get("status") or "",
        "priority": task.get("priority") or "",
        "module_name": task.get("module_name") or "",
        "department_name": task.get("department_name") or "",
        "project_name": task.get("project_name") or "",
        "due_date": due_str,
        "sla_status": task.get("sla_status") or "",
        "owner_name": (task.get("current_owner") or {}).get("name") or "",
        "team_lead_name": (task.get("team_lead") or {}).get("name") or "",
        "progress_pct": task.get("progress_pct") or 0,
    }


async def fetch_task_export_rows(db, user, filters=None) -> list:
    result = await list_tasks_query(db, user, filters or {}, skip=0, limit=5000)
    return [_row_from_task(t) for t in result["items"]]


async def export_tasks_csv(db, user, filters=None) -> str:
    rows = await fetch_task_export_rows(db, user, filters)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(TASK_HEADERS)
    for row in rows:
        writer.writerow([row[col] for col in TASK_COLUMNS])
    return buf.getvalue()


def build_tasks_xlsx(rows: list) -> bytes:
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    ws = wb.add_worksheet("Tasks")
    header_fmt = wb.add_format({"bold": True, "bg_color": "#0A1128", "font_color": "white", "border": 1})
    body_fmt = wb.add_format({"border": 1})
    for col, header in enumerate(TASK_HEADERS):
        ws.write(0, col, header, header_fmt)
    for row_idx, row in enumerate(rows, start=1):
        for col_idx, key in enumerate(TASK_COLUMNS):
            ws.write(row_idx, col_idx, row.get(key, ""), body_fmt)
    ws.set_column(0, len(TASK_COLUMNS) - 1, 18)
    wb.close()
    buf.seek(0)
    return buf.read()


def build_tasks_pdf(rows: list) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), title="Task Export")
    styles = getSampleStyleSheet()
    data = [TASK_HEADERS] + [[str(row.get(k, "")) for k in TASK_COLUMNS] for row in rows]
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A1128")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#94A3B8")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    doc.build([Paragraph("<b>Task Management Export</b>", styles["Title"]), Spacer(1, 12), table])
    buf.seek(0)
    return buf.read()


async def export_tasks_xlsx(db, user, filters=None) -> bytes:
    rows = await fetch_task_export_rows(db, user, filters)
    return build_tasks_xlsx(rows)


async def export_tasks_pdf(db, user, filters=None) -> bytes:
    rows = await fetch_task_export_rows(db, user, filters)
    return build_tasks_pdf(rows)
