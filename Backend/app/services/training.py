"""Background federated training jobs started from the UI (Federated Lab)."""

import json
import threading
import time

import torch

from app.config import ARTIFACT_DIR, META_PATH, MODEL_PATH, REPORT_PATH
from app.data import behavior
from app.ml.experiments import run_pipeline
from app.ml.federated import FedConfig
from app.services import datasets, store
from app.services.scoring import service

_state = {"status": "idle", "stage": "", "rounds": [], "config": None, "error": None, "result": None,
          "started": None, "promoted": False}
_lock = threading.Lock()


def status() -> dict:
    with _lock:
        return json.loads(json.dumps(_state))


def start(cfg: FedConfig, promote: bool, full: bool, owner_id: int) -> bool:
    with _lock:
        if _state["status"] == "running":
            return False
        _state.update(status="running", stage="preparing", rounds=[], config=cfg.dict(), error=None,
                      result=None, started=time.time(), promoted=False)
    threading.Thread(target=_run, args=(cfg, promote, full, owner_id), daemon=True).start()
    return True


def _run(cfg: FedConfig, promote: bool, full: bool, owner_id: int):
    def progress(p):
        with _lock:
            _state["stage"] = p["stage"]
            if "round" in p:
                _state["rounds"].append({k: p[k] for k in p if k != "note"})
                _state["rounds"] = _state["rounds"][-400:]

    try:
        uploaded, stored = store.latest_dataset(owner_id)
        if not uploaded:
            raise ValueError("Upload a labelled transaction dataset before starting federated training.")
        df = datasets.parse(uploaded["filename"], datasets.load_file(stored))
        df = behavior.compute(datasets.normalize_transactions(df))
        if "is_fraud" not in df.columns:
            raise ValueError("The uploaded training dataset must contain an is_fraud or fraud-label column.")
        if df["is_fraud"].nunique() < 2:
            raise ValueError("The uploaded training dataset must contain both legitimate and fraudulent rows.")
        active = uploaded["filename"]
        report, art = run_pipeline(df, cfg, progress=progress, full=full)
        report["dataset"]["name"] = art["meta"]["dataset"] = active
        if promote:
            ARTIFACT_DIR.mkdir(exist_ok=True)
            torch.save({"mlp": art["mlp"], "ae": art["ae"]}, MODEL_PATH)
            META_PATH.write_text(json.dumps(art["meta"], indent=2))
            if full:
                REPORT_PATH.write_text(json.dumps(report, indent=2))
            service.load()
        with _lock:
            _state.update(status="done", stage="finished", result={
                "metrics": report["final"]["metrics"], "experiments": {
                    k: {"label": v["label"], "metrics": v["metrics"]} for k, v in report["experiments"].items()},
                "duration_sec": report["duration_sec"]}, promoted=promote)
    except Exception as e:  # noqa: BLE001 - surfaced to the UI
        with _lock:
            _state.update(status="error", error=str(e))
