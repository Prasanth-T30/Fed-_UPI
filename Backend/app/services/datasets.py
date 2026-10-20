"""Parse uploaded dataset files (CSV, Excel, JSON, Word tables) into a DataFrame."""

import io
import re
import uuid
from pathlib import Path

import pandas as pd

from app.config import ROOT

STORAGE = ROOT / "storage" / "datasets"
ALLOWED = {".csv", ".xlsx", ".xlsm", ".json", ".docx", ".txt", ".tsv"}
MAX_BYTES = 10_000_000
MAX_ROWS = 20_000


def parse(filename: str, raw: bytes) -> pd.DataFrame:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED:
        raise ValueError(f"Unsupported file type {ext or '(none)'}. Use: {', '.join(sorted(ALLOWED))}")
    if ext in (".csv", ".txt"):
        df = pd.read_csv(io.BytesIO(raw), sep=None, engine="python")
    elif ext == ".tsv":
        df = pd.read_csv(io.BytesIO(raw), sep="\t")
    elif ext in (".xlsx", ".xlsm"):
        df = pd.read_excel(io.BytesIO(raw), engine="openpyxl")
    elif ext == ".json":
        df = pd.read_json(io.BytesIO(raw))
    else:  # .docx - first table with a header row
        from docx import Document
        doc = Document(io.BytesIO(raw))
        if not doc.tables:
            raise ValueError("The Word document contains no tables.")
        t = doc.tables[0]
        data = [[c.text.strip() for c in r.cells] for r in t.rows]
        df = pd.DataFrame(data[1:], columns=data[0])
        for col in df.columns:                      # Word tables are text: convert numeric-looking columns
            try:
                df[col] = pd.to_numeric(df[col])
            except (ValueError, TypeError):
                pass
    df.columns = [re.sub(r"[^a-z0-9]+", "_", str(c).strip().lower()).strip("_") for c in df.columns]
    df = df.dropna(how="all")
    if len(df) == 0:
        raise ValueError("The file has no data rows.")
    if len(df) > MAX_ROWS:
        raise ValueError(f"Too many rows ({len(df)}). Maximum is {MAX_ROWS}.")
    return df


def save_file(filename: str, raw: bytes) -> str:
    STORAGE.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex}{Path(filename).suffix.lower()}"
    (STORAGE / stored).write_bytes(raw)
    return stored


def load_file(stored: str) -> bytes:
    return (STORAGE / stored).read_bytes()


def remove_file(stored: str):
    (STORAGE / stored).unlink(missing_ok=True)
