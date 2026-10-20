"""Central paths and constants for FedUPI."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ARTIFACT_DIR = ROOT / "artifacts"
DB_URL = f"sqlite:///{(ROOT / 'fedupi.db').as_posix()}"
FRONTEND_DIST = ROOT.parent / "Frontend" / "dist"

DATASET_PATH = DATA_DIR / "upi_transactions.csv"
REPORT_PATH = ARTIFACT_DIR / "report.json"
MODEL_PATH = ARTIFACT_DIR / "fedupi_model.pt"
META_PATH = ARTIFACT_DIR / "fedupi_meta.json"

MODEL_VERSION = "fedupi-v2-fedavg-mlp-ae"
