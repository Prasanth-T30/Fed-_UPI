"""Background federated training jobs started from the UI (Federated Lab)."""

import json
import threading
import time

import torch

from app.config import ARTIFACT_DIR, DATASET_PATH, META_PATH, MODEL_PATH, REPORT_PATH
from app.data.generator import generate
from app.ml.experiments import run_pipeline
from app.ml.federated import FedConfig
from app.services.scoring import service

import pandas as pd

from app.data.paysim import SAMPLE_PATH

_state = {"status": "idle", "stage": "", "rounds": [], "config": None, "error": None, "result": None,
          "started": None, "promoted": False}
_lock = threading.Lock()


def status() -> dict:
    with _lock:
        return json.loads(json.dumps(_state))


def start(cfg: FedConfig, promote: bool, full: bool) -> bool:
    with _lock:
        if _state["status"] == "running":
            return False
        _state.update(status="running", stage="preparing", rounds=[], config=cfg.dict(), error=None,
                      result=None, started=time.time(), promoted=False)
    threading.Thread(target=_run, args=(cfg, promote, full), daemon=True).start()
    return True


def _run(cfg: FedConfig, promote: bool, full: bool):
    def progress(p):
        with _lock:
            _state["stage"] = p["stage"]
            if "round" in p:
                _state["rounds"].append({k: p[k] for k in p if k != "note"})
                _state["rounds"] = _state["rounds"][-400:]

    try:
        active = service.meta.get("dataset", "upi")
        if active == "paysim" and SAMPLE_PATH.exists():
            df = pd.read_csv(SAMPLE_PATH)
        else:
            active = "upi"
            df = pd.read_csv(DATASET_PATH) if DATASET_PATH.exists() else generate(cfg.seed)
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
