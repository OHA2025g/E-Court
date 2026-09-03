"""Rollup aggregation and init-period tests."""
import uuid
from datetime import datetime, timezone

import pytest
from conftest import _sync_db, auth_headers
from rollup import (
    financial_exact_totals_stages,
    financial_hc_rollup_stages,
    physical_national_totals_stages,
)
from seed_constants import (
    NSC_COMPONENT,
    NSC_FINANCIAL_COMPLEX,
    NSC_FINANCIAL_ROOMS,
)

HC = "Allahabad"
COMPONENT = "e-Sewa Kendras"
INDICATOR = f"TEST Rollup Indicator {uuid.uuid4().hex[:8]}"


def _period():
    return datetime.now(timezone.utc).strftime("%Y-%m")


DIST_A = "Prayagraj"
DIST_B = "Lucknow"


def _cleanup_physical(period: str):
    _sync_db.physical_entries.delete_many({
        "high_court": HC,
        "component": COMPONENT,
        "indicator": INDICATOR,
        "reporting_period": period,
    })


def test_esewa_rollup_uses_cpc_target_achieved():
    period = _period()
    _cleanup_physical(period)
    now = datetime.now(timezone.utc)
    base = {
        "high_court": HC, "component": COMPONENT, "indicator": INDICATOR,
        "reporting_period": period, "percent": None, "rag": "NA", "remarks": None,
        "created_by": "test", "created_at": now, "updated_by": "test", "updated_at": now,
        "target": None, "achieved": None,
        "target_dpr": 100, "achieved_ecommittee": 10,
    }
    _sync_db.physical_entries.insert_many([
        {**base, "district": DIST_A, "target_cpc": 40, "achieved_cpc": 30},
        {**base, "district": DIST_B, "target_cpc": 60, "achieved_cpc": 40},
    ])
    try:
        rolled = list(_sync_db.physical_entries.aggregate(
            physical_national_totals_stages({"high_court": HC, "reporting_period": period})
        ))
        assert rolled[0]["target"] == 100
        assert rolled[0]["achieved"] == 70
    finally:
        _cleanup_physical(period)


def test_national_totals_rollup_sums_districts():
    period = _period()
    _cleanup_physical(period)
    now = datetime.now(timezone.utc)
    base = {
        "high_court": HC, "component": COMPONENT, "indicator": INDICATOR,
        "reporting_period": period, "percent": None, "rag": "NA", "remarks": None,
        "created_by": "test", "created_at": now, "updated_by": "test", "updated_at": now,
    }
    _sync_db.physical_entries.insert_many([
        {**base, "district": DIST_A, "target": 40, "achieved": 30},
        {**base, "district": DIST_B, "target": 60, "achieved": 40},
    ])
    try:
        rolled = list(_sync_db.physical_entries.aggregate(
            physical_national_totals_stages({"high_court": HC, "reporting_period": period})
        ))
        assert rolled[0]["target"] == 100
        assert rolled[0]["achieved"] == 70
        assert rolled[0]["count"] == 1
    finally:
        _cleanup_physical(period)


def test_public_progress_endpoint_still_ok(client):
    r = client.get("/api/public/progress")
    assert r.status_code == 200
    assert "physical" in r.json()


def test_physical_init_period(admin_session):
    client = admin_session["client"]
    headers = auth_headers(admin_session["token"])
    period = _period()
    r = client.post("/api/physical/init-period", headers=headers, json={
        "high_court": HC,
        "reporting_period": period,
        "component": COMPONENT,
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["created"] >= 0
    assert data["skipped"] >= 0
    r2 = client.post("/api/physical/init-period", headers=headers, json={
        "high_court": HC,
        "reporting_period": period,
        "component": COMPONENT,
    })
    assert r2.status_code == 200
    assert r2.json()["created"] == 0
    assert r2.json()["skipped"] >= data["created"]


def test_financial_init_period_idempotent(admin_session):
    client = admin_session["client"]
    headers = auth_headers(admin_session["token"])
    period = _period()
    body = {"high_court": HC, "reporting_period": period}
    r1 = client.post("/api/financial/init-period", headers=headers, json=body)
    assert r1.status_code == 200, r1.text
    r2 = client.post("/api/financial/init-period", headers=headers, json=body)
    assert r2.status_code == 200, r2.text
    assert r2.json()["created"] == 0


def test_financial_hc_rollup_drops_duplicate_nsc_canonical():
    """Heatmap Released must not add canonical NSC on top of Rooms + Complex."""
    hc = "Gauhati – Arunachal Pradesh"
    period = "2099-01"
    q = {"high_court": hc, "reporting_period": period}
    _sync_db.financial_entries.delete_many(q)
    rooms_rupees = 826_887.0
    complex_rupees = 5_244_502.0
    cloud_rupees = 11_710_994.96
    other_rupees = 193_307_448.0 - rooms_rupees - complex_rupees
    canonical_cr = 0.6071  # 4dp round of rooms+complex; the duplicate
    try:
        _sync_db.financial_entries.insert_many([
            {
                **q, "district": None, "component": NSC_COMPONENT,
                "fund_released": canonical_cr, "fund_utilized": 0.2022,
            },
            {
                **q, "district": None, "component": NSC_FINANCIAL_ROOMS,
                "fund_released": rooms_rupees / 1e7, "fund_released_rupees": rooms_rupees,
                "fund_utilized": rooms_rupees / 1e7, "fund_utilized_rupees": rooms_rupees,
            },
            {
                **q, "district": None, "component": NSC_FINANCIAL_COMPLEX,
                "fund_released": complex_rupees / 1e7, "fund_released_rupees": complex_rupees,
                "fund_utilized": 1_195_193 / 1e7, "fund_utilized_rupees": 1_195_193,
            },
            {
                **q, "district": None, "component": "Cloud Computing & Storage",
                "fund_released": cloud_rupees / 1e7, "fund_released_rupees": cloud_rupees,
                "fund_utilized": 2_545_224.23 / 1e7, "fund_utilized_rupees": 2_545_224.23,
            },
            {
                **q, "district": None, "component": "e-Sewa Kendras",
                "fund_released": other_rupees / 1e7, "fund_released_rupees": other_rupees,
                "fund_utilized": 0, "fund_utilized_rupees": 0,
            },
        ])
        hc_rows = list(_sync_db.financial_entries.aggregate(financial_hc_rollup_stages(q)))
        assert len(hc_rows) == 1
        expected = (rooms_rupees + complex_rupees + cloud_rupees + other_rupees) / 1e7
        assert hc_rows[0]["r"] == pytest.approx(expected, rel=0, abs=1e-9)
        inflated = expected + canonical_cr
        assert hc_rows[0]["r"] != pytest.approx(inflated, abs=0.001)
        assert hc_rows[0]["r"] == pytest.approx(20.501844296, abs=1e-9)

        totals = list(_sync_db.financial_entries.aggregate(financial_exact_totals_stages(q)))
        assert totals[0]["released"] == pytest.approx(expected, rel=0, abs=1e-9)
    finally:
        _sync_db.financial_entries.delete_many(q)


def test_financial_hc_rollup_keeps_canonical_nsc_when_no_split():
    hc = "Sikkim"
    period = "2099-02"
    q = {"high_court": hc, "reporting_period": period}
    _sync_db.financial_entries.delete_many(q)
    try:
        _sync_db.financial_entries.insert_one({
            **q, "district": None, "component": NSC_COMPONENT,
            "fund_released": 1.1095, "fund_released_rupees": 11_095_000,
            "fund_utilized": 0.5, "fund_utilized_rupees": 5_000_000,
        })
        rows = list(_sync_db.financial_entries.aggregate(financial_hc_rollup_stages(q)))
        assert rows[0]["r"] == pytest.approx(1.1095, abs=1e-9)
    finally:
        _sync_db.financial_entries.delete_many(q)
