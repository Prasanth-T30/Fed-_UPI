"""Export flagged transactions as CSV, Excel, Word, PDF or JSON."""

import io
import json
import re
import time

import pandas as pd

FORMATS = {
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
    "json": "application/json",
}
COLS = ["reference", "time_utc", "amount_inr", "risk_percent", "decision", "why_flagged"]
HEAD = ["Reference", "Transaction time (UTC)", "Amount (INR)", "Risk %", "Action", "Why flagged"]


def _concise_reasons(reasons: list) -> str:
    items = []
    for item in reasons or []:
        reason = str(item.get("reason", "")).strip()
        if not reason or reason in items:
            continue
        if reason.startswith("Large amount") and any(x.startswith("Amount Rs") for x in items):
            continue
        ratio = re.search(r"Amount is ([\d.]+)x", reason)
        if ratio and float(ratio.group(1)) <= 1.2:
            continue
        items.append(reason)
        if len(items) == 2:
            break
    return " | ".join(items) or "Model-detected suspicious pattern"


def to_frame(rows: list) -> pd.DataFrame:
    records = [{
        "reference": r.get("txn_ref") or "-",
        "time_utc": r.get("txn_time") or r.get("created_at") or "-",
        "amount_inr": round(float(r.get("amount") or 0), 2),
        "risk_percent": round(float(r.get("risk_score") or 0), 1),
        "decision": r.get("decision") or "REVIEW",
        "why_flagged": _concise_reasons(r.get("reasons") or []),
    } for r in rows]
    df = pd.DataFrame(records, columns=COLS)
    df["time_utc"] = df["time_utc"].astype(str).str.replace("T", " ", regex=False).str.replace("Z", "", regex=False).str[:19]
    rank = df["decision"].map({"BLOCK": 0, "STEP_UP_AUTH": 1, "ALLOW": 2}).fillna(3)
    return (df.assign(_rank=rank)
            .sort_values(["_rank", "risk_percent", "time_utc"], ascending=[True, False, False], kind="stable")
            .drop(columns="_rank").reset_index(drop=True))


def build(rows: list, fmt: str, title: str = "FedUPI flagged transactions"):
    if fmt not in FORMATS:
        raise ValueError("Unsupported format")
    df = to_frame(rows)
    stamp = time.strftime("%Y%m%d-%H%M")
    name = f"fedupi-flagged-{stamp}.{fmt}"
    buf = io.BytesIO()
    if fmt == "csv":
        buf.write(df.rename(columns=dict(zip(COLS, HEAD))).to_csv(index=False).encode("utf-8-sig"))
    elif fmt == "json":
        buf.write(json.dumps(df.to_dict(orient="records"), indent=2, default=str).encode())
    elif fmt == "xlsx":
        from openpyxl.styles import Alignment, Font, PatternFill

        with pd.ExcelWriter(buf, engine="openpyxl") as xw:
            out = df.rename(columns=dict(zip(COLS, HEAD)))
            out.to_excel(xw, index=False, sheet_name="Flagged")
            ws = xw.sheets["Flagged"]
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            widths = [18, 23, 16, 11, 18, 65]
            for index, width in enumerate(widths, 1):
                ws.column_dimensions[ws.cell(1, index).column_letter].width = width
            for cell in ws[1]:
                cell.fill = PatternFill("solid", fgColor="4F46E5")
                cell.font = Font(color="FFFFFF", bold=True)
                cell.alignment = Alignment(vertical="center")
            ws.row_dimensions[1].height = 24
            for row in range(2, ws.max_row + 1):
                if row % 2 == 0:
                    for cell in ws[row]:
                        cell.fill = PatternFill("solid", fgColor="F3F4F6")
                ws.cell(row, 3).number_format = '#,##0.00'
                ws.cell(row, 4).number_format = '0.0'
                ws.cell(row, 6).alignment = Alignment(wrap_text=True, vertical="top")
                ws.row_dimensions[row].height = 30
    elif fmt == "docx":
        from docx import Document
        from docx.shared import Pt
        d = Document()
        d.add_heading(title, 1)
        d.add_paragraph(f"Generated {time.strftime('%Y-%m-%d %H:%M')} UTC | {len(df)} transactions")
        t = d.add_table(rows=1, cols=len(HEAD)); t.style = "Light Grid Accent 1"
        for i, h in enumerate(HEAD):
            t.rows[0].cells[i].text = h
        for rec in df.itertuples(index=False):
            cells = t.add_row().cells
            for i, v in enumerate(rec):
                cells[i].text = str(v)
        for row in t.rows:
            for c in row.cells:
                for p in c.paragraphs:
                    for r in p.runs:
                        r.font.size = Pt(7)
        d.save(buf)
    else:  # pdf
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        st = getSampleStyleSheet()
        doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24)
        small = st["BodyText"].clone("s"); small.fontSize = 6.5; small.leading = 8
        shown = df.head(1000)
        data = [HEAD] + [[Paragraph(str(v), small) for v in r] for r in shown.itertuples(index=False)]
        tbl = Table(data, repeatRows=1, colWidths=[72, 94, 68, 42, 72, 392])
        tbl.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4f46e5")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                                 ("FONTSIZE", (0, 0), (-1, 0), 7), ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                                 ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        note = f"{len(df)} transactions" + (" (first 1000 shown)" if len(df) > 1000 else "")
        doc.build([Paragraph(title, st["Title"]), Paragraph(f"Generated {time.strftime('%Y-%m-%d %H:%M')} UTC | {note}", st["BodyText"]), Spacer(1, 8), tbl])
    return buf.getvalue(), FORMATS[fmt], name
