"""Cabinet brief PDF generation (shared by export route and scheduled job)."""
import io
from typing import Callable, Optional
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4 as A4_PORTRAIT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from rollup import (
    financial_hc_rollup_stages,
    financial_national_totals_stages,
    outcome_hc_rollup_stages,
    outcome_rollup_stages,
    physical_hc_rollup_stages,
    physical_national_totals_stages,
    physical_rollup_stages,
)


def _append_numbered_list(story, title, items, title_style, body_style) -> None:
    story.append(Paragraph(title, title_style))
    if not items:
        story.append(Paragraph("No items available.", body_style))
        story.append(Spacer(1, 4))
        return
    for i, item in enumerate(items, 1):
        story.append(Paragraph(f"{i}. {escape(str(item))}", body_style))
    story.append(Spacer(1, 4))


def _append_action_plan(story, phases, title_style, body_style, phase_style) -> None:
    story.append(Paragraph("Action Plan", title_style))
    if not phases:
        story.append(Paragraph("No action plan available.", body_style))
        story.append(Spacer(1, 4))
        return
    for phase in phases:
        phase_name = escape(str(phase.get("phase", "Phase")))
        story.append(Paragraph(f"<b>{phase_name}</b>", phase_style))
        for action in phase.get("actions") or []:
            story.append(Paragraph(f"• {escape(str(action))}", body_style))
        story.append(Spacer(1, 2))
    story.append(Spacer(1, 2))


async def _load_ai_executive_brief(
    db,
    summary: dict,
    reporting_period: Optional[str],
    extra_match: Optional[dict],
    generated_by: str,
    compute_rag_fn: Callable,
    safe_div_fn: Callable,
) -> dict:
    from dashboard_agg import (
        compute_dashboard_by_component,
        compute_dashboard_by_hc,
        compute_pareto_red_flags,
        compute_rag_delta,
    )
    from dashboard_insights import generate_insights_payload

    viewer = {"role": "Viewer", "email": generated_by}
    scope = lambda u: {}

    by_component = await compute_dashboard_by_component(
        db, scope, safe_div_fn, viewer, reporting_period, extra_match,
    )
    by_hc = await compute_dashboard_by_hc(
        db, scope, safe_div_fn, viewer, reporting_period, extra_match,
    )
    rag_delta = None
    try:
        rag_delta = await compute_rag_delta(
            db, scope, compute_rag_fn, safe_div_fn, viewer, reporting_period, "physical", extra_match,
        )
    except Exception:
        pass
    pareto = await compute_pareto_red_flags(
        db, scope, compute_rag_fn, viewer, reporting_period, "physical", extra_match,
    )
    return await generate_insights_payload(
        db, summary, by_component, by_hc, rag_delta, pareto, reporting_period, viewer, refresh=False,
    )


async def build_cabinet_brief_pdf(
    db,
    reporting_period: Optional[str],
    generated_by: str,
    compute_rag_fn: Callable,
    safe_div_fn: Callable,
    now_utc_fn: Callable,
    default_rag_thresholds: dict,
    extra_match: Optional[dict] = None,
) -> bytes:
    """Build the Cabinet Brief PDF and return raw bytes."""
    from period_policy import merge_match

    pmatch: dict = {}
    fmatch: dict = {}
    if reporting_period:
        pmatch["reporting_period"] = reporting_period
        fmatch["reporting_period"] = reporting_period
    if extra_match:
        pmatch = merge_match(pmatch, extra_match)
        fmatch = merge_match(fmatch, extra_match)

    phys_agg = await db.physical_entries.aggregate(physical_national_totals_stages(pmatch)).to_list(1)
    fin_agg = await db.financial_entries.aggregate(financial_national_totals_stages(fmatch)).to_list(1)
    thresholds = (await db.settings.find_one({"key": "rag_thresholds"}) or {}).get("value", default_rag_thresholds)

    rolled_phys = await db.physical_entries.aggregate(physical_rollup_stages(pmatch)).to_list(50000)
    rag_map: dict = {}
    for row in rolled_phys:
        pct = safe_div_fn(row.get("achieved"), row.get("target"))
        status = compute_rag_fn(pct, thresholds)
        rag_map[status] = rag_map.get(status, 0) + 1

    hc_rows = await db.physical_entries.aggregate(physical_hc_rollup_stages(pmatch)).to_list(50)
    phys_ranked = []
    for r in hc_rows:
        pct = safe_div_fn(r["a"], r["t"])
        if pct is not None:
            phys_ranked.append((r["_id"], pct))
    phys_ranked.sort(key=lambda x: x[1], reverse=True)
    top5, bottom5 = phys_ranked[:5], phys_ranked[-5:][::-1] if len(phys_ranked) >= 5 else phys_ranked[::-1]

    fin_hc_rows = await db.financial_entries.aggregate(financial_hc_rollup_stages(fmatch)).to_list(50)
    fin_ranked = []
    for r in fin_hc_rows:
        pct = safe_div_fn(r["u"], r["r"])
        if pct is not None:
            fin_ranked.append((r["_id"], pct))
    fin_ranked.sort(key=lambda x: x[1], reverse=True)
    fin_top5, fin_bottom5 = fin_ranked[:5], fin_ranked[-5:][::-1] if len(fin_ranked) >= 5 else fin_ranked[::-1]

    omatch: dict = {}
    if reporting_period:
        omatch["reporting_period"] = reporting_period
    outcome_rolled = await db.outcome_entries.aggregate(outcome_rollup_stages(omatch)).to_list(50000)
    outcome_reported = sum(1 for row in outcome_rolled if row.get("value") is not None)
    outcome_total = len(outcome_rolled)
    outcome_pct = safe_div_fn(outcome_reported, outcome_total)

    outcome_hc_rows = await db.outcome_entries.aggregate(outcome_hc_rollup_stages(omatch)).to_list(50)
    outcome_hc_ranked = []
    for r in outcome_hc_rows:
        pct = safe_div_fn(r.get("reported"), r.get("total"))
        if pct is not None and r.get("total", 0) > 0:
            outcome_hc_ranked.append((r["_id"], pct, r.get("reported", 0), r.get("total", 0)))
    outcome_hc_ranked.sort(key=lambda x: x[1], reverse=True)
    outcome_top5 = outcome_hc_ranked[:5]
    outcome_bottom5 = outcome_hc_ranked[-5:][::-1] if len(outcome_hc_ranked) >= 5 else outcome_hc_ranked[::-1]
    rag_map = rag_map or {"NA": 0}

    p = phys_agg[0] if phys_agg else {"target": 0, "achieved": 0, "count": 0}
    f = fin_agg[0] if fin_agg else {"released": 0, "utilized": 0, "target": 0}

    from dashboard_agg import compute_dashboard_summary
    from narrative import narrative_for_export

    summary = await compute_dashboard_summary(
        db, lambda u: {}, compute_rag_fn, safe_div_fn,
        {"role": "Viewer", "email": generated_by}, reporting_period, extra_match,
    )
    narrative_text = await narrative_for_export(db, summary, reporting_period)
    ai_brief = await _load_ai_executive_brief(
        db, summary, reporting_period, extra_match, generated_by, compute_rag_fn, safe_div_fn,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4_PORTRAIT, title="eCourts Phase III — Cabinet Brief",
                             topMargin=15 * mm, bottomMargin=15 * mm,
                             leftMargin=15 * mm, rightMargin=15 * mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("t1", parent=styles["Title"], fontSize=16, leading=20, alignment=0,
                                  textColor=colors.HexColor("#0A1128"), spaceAfter=2)
    sub_style = ParagraphStyle("sub", parent=styles["Normal"], fontSize=8, leading=10,
                                textColor=colors.HexColor("#475569"), spaceAfter=8)
    sec_style = ParagraphStyle("sec", parent=styles["Heading2"], fontSize=10, leading=12,
                                textColor=colors.HexColor("#0A1128"), spaceBefore=8, spaceAfter=4)
    subsec_style = ParagraphStyle("subsec", parent=styles["Heading3"], fontSize=9, leading=11,
                                   textColor=colors.HexColor("#0A1128"), spaceBefore=6, spaceAfter=3)
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=8, leading=11)
    story = []

    def _hc_table(title, rows, header_bg, row_bg, col_label="Physical %"):
        story.append(Paragraph(title, sec_style))
        if not rows:
            story.append(Paragraph("Insufficient data.", body))
            return
        if len(rows[0]) == 2:
            data = [["Rank", "High Court", col_label]] + [[i + 1, h, f"{p_:.1f}%"] for i, (h, p_) in enumerate(rows)]
            widths = [15 * mm, 80 * mm, 30 * mm]
        else:
            data = [["Rank", "High Court", "Reported", "Total", "Reporting %"]] + [
                [i + 1, h, str(rep), str(tot), f"{p_:.1f}%"]
                for i, (h, p_, rep, tot) in enumerate(rows)
            ]
            widths = [12 * mm, 55 * mm, 22 * mm, 22 * mm, 28 * mm]
        tbl = Table(data, colWidths=widths)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_bg)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#94A3B8")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(row_bg)]),
        ]))
        story.append(tbl)

    story.append(Paragraph("eCourts Phase III — Project Monitoring Brief", title_style))
    story.append(Paragraph(
        f"Department of Justice · PMU · e-Committee &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"Reporting Period: <b>{reporting_period or 'All periods'}</b> &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"Generated: {now_utc_fn().strftime('%d %b %Y, %H:%M UTC')} &nbsp;&nbsp;|&nbsp;&nbsp; By: {generated_by}",
        sub_style))

    story.append(Paragraph("AI Executive Brief", sec_style))
    if ai_brief.get("source") == "mistral":
        brief_source = f"Powered by {ai_brief.get('model') or 'Mistral AI'} · based on approved dashboard data"
    else:
        brief_source = "Rule-based analysis · based on approved dashboard data"
    story.append(Paragraph(brief_source, sub_style))

    story.append(Paragraph("Executive Narrative", subsec_style))
    story.append(Paragraph(escape(narrative_text).replace("\n", "<br/>"), body))
    story.append(Spacer(1, 6))

    _append_numbered_list(story, "Insights", ai_brief.get("insights"), subsec_style, body)
    _append_numbered_list(story, "Recommendations", ai_brief.get("recommendations"), subsec_style, body)
    _append_numbered_list(story, "Action Items", ai_brief.get("action_items"), subsec_style, body)
    _append_action_plan(story, ai_brief.get("action_plan"), subsec_style, body, body)
    story.append(Spacer(1, 10))

    story.append(Paragraph("National KPI Summary", sec_style))

    kpi_data = [
        ["Physical Target", "Physical Achieved", "Physical %", "Funds Released (₹ Cr)", "Funds Utilised (₹ Cr)", "Utilisation %"],
        [
            f"{int(p['target']):,}",
            f"{int(p['achieved']):,}",
            f"{safe_div_fn(p['achieved'], p['target']) or 0:.1f}%",
            f"{f['released']:,.2f}",
            f"{f['utilized']:,.2f}",
            f"{safe_div_fn(f['utilized'], f['released']) or 0:.1f}%",
        ],
    ]
    kpi_tbl = Table(kpi_data, colWidths=[30 * mm] * 6, rowHeights=[8 * mm, 12 * mm])
    kpi_tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A1128")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 1), (-1, 1), 12),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#0A1128")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#94A3B8")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
    ]))
    story.append(kpi_tbl)
    story.append(Spacer(1, 8))

    story.append(Paragraph("Outcome KPI Reporting", sec_style))
    outcome_tbl = Table(
        [["Total KPIs", "Reported", "Reporting %"],
         [str(outcome_total), str(outcome_reported), f"{outcome_pct or 0:.1f}%"]],
        colWidths=[50 * mm, 50 * mm, 50 * mm], rowHeights=[8 * mm, 10 * mm],
    )
    outcome_tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A1128")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#94A3B8")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
    ]))
    story.append(outcome_tbl)
    story.append(Spacer(1, 8))

    _hc_table("Top 5 High Courts (Outcome reporting %)", outcome_top5, "#0A1128", "#ECFDF5")
    _hc_table("Bottom 5 High Courts (Outcome reporting %)", outcome_bottom5, "#7C2D12", "#FEF2F2")
    _hc_table("Top 5 High Courts (Financial utilisation %)", fin_top5, "#0A1128", "#FFFBEB", "Utilisation %")
    _hc_table("Bottom 5 High Courts (Financial utilisation %)", fin_bottom5, "#7C2D12", "#FEF2F2", "Utilisation %")

    story.append(Paragraph("Physical RAG Distribution (indicator-level)", sec_style))
    rag_total = sum(rag_map.values()) or 1
    rag_data = [["Status", "Indicators", "Share"]]
    for k in ["GREEN", "AMBER", "RED", "NA"]:
        n = rag_map.get(k, 0)
        rag_data.append([k, str(n), f"{(n / rag_total) * 100:.1f}%"])
    rag_tbl = Table(rag_data, colWidths=[40 * mm, 40 * mm, 40 * mm])
    rag_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A1128")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#94A3B8")),
        ("BACKGROUND", (0, 1), (0, 1), colors.HexColor("#D1FAE5")),
        ("BACKGROUND", (0, 2), (0, 2), colors.HexColor("#FEF3C7")),
        ("BACKGROUND", (0, 3), (0, 3), colors.HexColor("#FEE2E2")),
        ("BACKGROUND", (0, 4), (0, 4), colors.HexColor("#F1F5F9")),
    ]))
    story.append(rag_tbl)

    _hc_table("Top 5 High Courts (Physical %)", top5, "#0A1128", "#F1F5F9")
    _hc_table("Bottom 5 High Courts (Physical %)", bottom5, "#7C2D12", "#FEF2F2")

    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"<i>Source: eCourts PMIS · Indicators tracked: {p['count']} · Outcome KPIs: {outcome_total} "
        f"({outcome_reported} reported) · "
        f"This brief is system-generated; refer to detailed tracker reports for evidence-level drill-down.</i>",
        ParagraphStyle("f", parent=body, fontSize=7, textColor=colors.HexColor("#64748B"))))

    doc.build(story)
    buf.seek(0)
    return buf.read()
