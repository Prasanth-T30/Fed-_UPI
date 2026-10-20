"""Export flagged transactions as CSV, Excel, Word, PDF or JSON."""

import io
import json
import time

import pandas as pd

FORMATS = {
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
    "json": "application/json",
}
COLS = ["txn_ref", "created_at", "bank", "category", "amount", "risk_score", "risk_level", "decision", "status", "top_reasons"]
HEAD = ["Reference", "Time (UTC)", "Bank", "Category", "Amount (INR)", "Risk %", "Risk tier", "Decision", "Review status", "Why flagged"]


def to_frame(rows: list) -> pd.DataFrame:
    df = pd.DataFrame([{
        **{k: r.get(k) for k in COLS[:-1]},
        "top_reasons": "; ".join(x["reason"] for x in (r.get("reasons") or [])[:3]),
    } for r in rows], columns=COLS)
    df["created_at"] = df["created_at"].astype(str).str.replace("T", " ").str[:19]
    return df


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
        buf.write(json.dumps(rows, indent=2, default=str).encode())
    elif fmt == "xlsx":
        with pd.ExcelWriter(buf, engine="openpyxl") as xw:
            out = df.rename(columns=dict(zip(COLS, HEAD)))
            out.to_excel(xw, index=False, sheet_name="Flagged")
            ws = xw.sheets["Flagged"]
            for i, c in enumerate(out.columns, 1):
                ws.column_dimensions[ws.cell(1, i).column_letter].width = min(60, max(12, int(out[c].astype(str).str.len().max() or 10) + 2))
            ws.freeze_panes = "A2"
    elif fmt == "docx":
        from docx import Document
        from docx.shared import Pt
        d = Document()
        d.add_heading(title, 1)
        d.add_paragraph(f"Generated {time.strftime('%Y-%m-%d %H:%M')} · {len(df)} transactions")
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
        tbl = Table(data, repeatRows=1, colWidths=[62, 66, 40, 48, 56, 40, 36, 60, 56, 300])
        tbl.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4f46e5")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                                 ("FONTSIZE", (0, 0), (-1, 0), 7), ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                                 ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        note = f"{len(df)} transactions" + (" (first 1000 shown)" if len(df) > 1000 else "")
        doc.build([Paragraph(title, st["Title"]), Paragraph(f"Generated {time.strftime('%Y-%m-%d %H:%M')} · {note}", st["BodyText"]), Spacer(1, 8), tbl])
    return buf.getvalue(), FORMATS[fmt], name
