"""Bulk Excel upload tests for physical, financial, and outcome trackers."""
import io
from datetime import datetime, timezone

import openpyxl
from conftest import auth_headers


HC = "Allahabad"
COMPONENT = "e-Sewa Kendras"
INDICATOR = "No of sites prepared (in Absolute Count)"
PERIOD = datetime.now(timezone.utc).strftime("%Y-%m")


def _xlsx_bytes(headers, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_physical_bulk_dry_run_and_commit(admin_session):
    client = admin_session["client"]
    headers = auth_headers(admin_session["token"])
    raw = _xlsx_bytes(
        ["High Court", "Component", "Sub-Component", "District", "Target", "Achieved", "Remarks"],
        [[HC, COMPONENT, INDICATOR, "Prayagraj", 200, 150, "bulk test"]],
    )
    files = {"file": ("physical.xlsx", raw, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    preview = client.post(
        f"/api/physical/bulk?reporting_period={PERIOD}&dry_run=true",
        headers=headers, files=files,
    )
    assert preview.status_code == 200, preview.text
    data = preview.json()
    assert data["dry_run"] is True
    assert data["summary"]["valid"] >= 1
    assert any(r.get("status") == "ok" for r in data.get("rows", []))

    commit = client.post(
        f"/api/physical/bulk?reporting_period={PERIOD}&dry_run=false",
        headers=headers, files=files,
    )
    assert commit.status_code == 200, commit.text
    assert commit.json()["inserted"] + commit.json()["updated"] >= 1


def test_physical_bulk_preview_token_commit(admin_session):
    client = admin_session["client"]
    headers = auth_headers(admin_session["token"])
    raw = _xlsx_bytes(
        ["High Court", "Component", "Sub-Component", "District", "Target", "Achieved", "Remarks"],
        [[HC, COMPONENT, INDICATOR, "Varanasi", 80, 40, "token flow"]],
    )
    files = {"file": ("physical.xlsx", raw, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    preview = client.post(
        f"/api/physical/bulk?reporting_period={PERIOD}&dry_run=true",
        headers=headers, files=files,
    )
    assert preview.status_code == 200, preview.text
    token = preview.json().get("preview_token")
    assert token

    commit = client.post(
        f"/api/physical/bulk?reporting_period={PERIOD}&dry_run=false&preview_token={token}",
        headers=headers,
    )
    assert commit.status_code == 200, commit.text
    assert commit.json()["inserted"] + commit.json()["updated"] >= 1


def test_financial_bulk_invalid_row(admin_session):
    client = admin_session["client"]
    headers = auth_headers(admin_session["token"])
    raw = _xlsx_bytes(
        ["High Court", "Component", "District", "Fund Released", "Fund Utilized", "Remarks"],
        [[HC, COMPONENT, "", "not-a-number", 5, "bad"]],
    )
    files = {"file": ("financial.xlsx", raw, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = client.post(
        f"/api/financial/bulk?reporting_period={PERIOD}&dry_run=true",
        headers=headers, files=files,
    )
    assert r.status_code == 200, r.text
    assert r.json()["summary"]["invalid"] >= 1 or r.json()["skipped"] >= 1


def test_outcome_bulk_unknown_kpi_skipped(admin_session):
    client = admin_session["client"]
    headers = auth_headers(admin_session["token"])
    raw = _xlsx_bytes(
        ["High Court", "Subject", "KPI ID", "Granularity", "District", "Value", "Baseline", "Remarks"],
        [[HC, "eFiling", "NONEXISTENT-KPI", "District", "Prayagraj", 42, "", ""]],
    )
    files = {"file": ("outcome.xlsx", raw, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = client.post(
        f"/api/outcome/bulk?reporting_period={PERIOD}&dry_run=true",
        headers=headers, files=files,
    )
    assert r.status_code == 200, r.text
    assert r.json()["summary"]["invalid"] >= 1 or r.json()["skipped"] >= 1


def test_outcome_bulk_district_required(admin_session):
    client = admin_session["client"]
    headers = auth_headers(admin_session["token"])
    raw = _xlsx_bytes(
        ["High Court", "Subject", "KPI ID", "Granularity", "District", "Value", "Baseline", "Remarks"],
        [[HC, "eFiling", "EF-01", "District", "", 10, "", "missing district"]],
    )
    files = {"file": ("outcome.xlsx", raw, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = client.post(
        f"/api/outcome/bulk?reporting_period={PERIOD}&dry_run=true",
        headers=headers, files=files,
    )
    assert r.status_code == 200, r.text
    assert r.json()["summary"]["invalid"] >= 1 or r.json()["skipped"] >= 1


def test_viewer_bulk_dry_run_forbidden(viewer_session):
    client = viewer_session["client"]
    headers = auth_headers(viewer_session["token"])
    raw = _xlsx_bytes(
        ["High Court", "Component", "Sub-Component", "District", "Target", "Achieved", "Remarks"],
        [[HC, COMPONENT, INDICATOR, "", 10, 5, ""]],
    )
    files = {"file": ("physical.xlsx", raw, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = client.post(
        f"/api/physical/bulk?reporting_period={PERIOD}&dry_run=true",
        headers=headers, files=files,
    )
    assert r.status_code == 403
