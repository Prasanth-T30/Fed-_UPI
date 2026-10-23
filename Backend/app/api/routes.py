"""REST API."""

import json
from typing import Literal

import pandas as pd
from flask import Blueprint, Response, request
from pydantic import BaseModel, Field, ValidationError
from werkzeug.exceptions import BadRequest, Conflict, NotFound, RequestEntityTooLarge, ServiceUnavailable, UnprocessableEntity

from app.config import MODEL_VERSION, REPORT_PATH
from app.data import behavior
from app.data.features import OPTIONAL, REQUIRED
from app.ml.federated import FedConfig
from app.services import datasets, exports, store, training
from app.services.auth import current_user
from app.services.scoring import service

router = Blueprint("api", __name__, url_prefix="/api")
public = Blueprint("public", __name__, url_prefix="/api")


@router.before_request
def require_login():
    current_user()


def body(model):
    try:
        return model.model_validate(request.get_json(silent=True) or {})
    except ValidationError as error:
        raise UnprocessableEntity("; ".join(item["msg"] for item in error.errors())) from error


def integer_arg(name):
    value = request.args.get(name)
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError as error:
        raise UnprocessableEntity(f"{name} must be an integer.") from error

PAPERS = [
    {"title": "Communication-Efficient Learning of Deep Networks from Decentralized Data (FedAvg)",
     "authors": "McMahan et al.", "venue": "AISTATS 2017", "url": "https://proceedings.mlr.press/v54/mcmahan17a.html",
     "used_for": "Core federated averaging used to combine bank models."},
    {"title": "Federated Optimization in Heterogeneous Networks (FedProx)", "authors": "Li et al.",
     "venue": "MLSys 2020", "url": "https://arxiv.org/abs/1812.06127",
     "used_for": "Proximal term that stabilises training when banks have different fraud patterns (non-IID)."},
    {"title": "Learning Differentially Private Recurrent Language Models (DP-FedAvg)", "authors": "McMahan et al.",
     "venue": "ICLR 2018", "url": "https://arxiv.org/abs/1710.06963",
     "used_for": "Update clipping + Gaussian noise used in the privacy option."},
    {"title": "Practical Secure Aggregation for Privacy-Preserving Machine Learning", "authors": "Bonawitz et al.",
     "venue": "ACM CCS 2017", "url": "https://eprint.iacr.org/2017/281", "used_for": "Future work: secure aggregation of updates."},
    {"title": "Federated Machine Learning: Concept and Applications", "authors": "Yang, Liu, Chen, Tong",
     "venue": "ACM TIST 2019", "url": "https://arxiv.org/abs/1902.04885", "used_for": "Horizontal federated learning across institutions."},
    {"title": "FFD: A Federated Learning Based Method for Credit Card Fraud Detection", "authors": "Yang et al.",
     "venue": "Big Data - BigData 2019", "url": "https://link.springer.com/chapter/10.1007/978-3-030-23551-2_2",
     "used_for": "Federated fraud detection across banks; closest classic baseline."},
    {"title": "Privacy-Preserving Federated Fraud Detection in Payment Transactions with NVIDIA FLARE",
     "authors": "arXiv 2603.13617", "venue": "arXiv 2026", "url": "https://arxiv.org/abs/2603.13617",
     "used_for": "Federated vs centralized vs local-only comparison, interpretability and DP trade-offs."},
    {"title": "FedUpi: Federated Learning for Fraudulent UPI Transaction Detection", "authors": "Sreeji et al.",
     "venue": "IJRASET 2026", "url": "https://www.ijraset.com/best-journal/fedupi-federated-learning-for-fraud-detection",
     "used_for": "UPI-specific velocity features and imbalance handling."},
    {"title": "Hybrid Deep Learning Models for Real-Time UPI Fraud Detection", "authors": "IJRASET review",
     "venue": "IJRASET", "url": "https://www.ijraset.com/research-paper/hybrid-deep-learning-models-for-real-time-upi-fraud-detection",
     "used_for": "Motivation: lack of public UPI datasets, case for federated approaches."},
    {"title": "Federated Learning for Fraud Detection: Credit Card and Banking", "authors": "ITM Web Conf. 2025",
     "venue": "DAI 2024", "url": "https://www.itm-conferences.org/10.1051/itmconf/20257003030",
     "used_for": "Survey of cross-institution federated fraud detection."},
]


class TxnIn(BaseModel):
    amount_inr: float = Field(ge=1, le=10_000_000)
    amount_to_average_ratio: float = Field(1.0, ge=0, le=100)
    transaction_hour: int = Field(14, ge=0, le=23)
    account_age_days: int = Field(800, ge=0)
    transactions_last_hour: int = Field(0, ge=0)
    minutes_since_last_transaction: float = Field(300, ge=0)
    failed_login_attempts_24h: int = Field(0, ge=0)
    upi_pin_failures_24h: int = Field(0, ge=0)
    is_new_device: Literal[0, 1] = 0
    is_new_beneficiary: Literal[0, 1] = 0
    is_collect_request: Literal[0, 1] = 0
    is_weekend: Literal[0, 1] = 0
    merchant_category: Literal["p2p", "merchant", "investment"] = "p2p"
    bank: str = "-"
    sender_id: str = Field("", max_length=60)             # with receiver_id: repeat history is read from stored payments
    receiver_id: str = Field("", max_length=60)
    sender_txn_24h: int = Field(0, ge=0)                  # manual override / extra known history
    same_receiver_24h: int = Field(0, ge=0)
    balance_drain: float = Field(0.0, ge=0, le=1)      # optional: amount / sender balance (PaySim model)
    dest_empty: Literal[0, 1] = 0                     # optional: beneficiary account empty before payment


class TrainIn(BaseModel):
    algorithm: Literal["fedavg", "fedprox"] = "fedavg"
    rounds: int = Field(12, ge=1, le=40)
    local_epochs: int = Field(2, ge=1, le=5)
    lr: float = Field(0.01, gt=0, le=0.2)
    mu: float = Field(0.01, ge=0, le=1)
    dp_clip: float = Field(0.0, ge=0, le=10)
    dp_noise: float = Field(0.0, ge=0, le=5)
    secure_agg: bool = False
    dp_delta: float = Field(1e-5, gt=0, lt=1)
    full_comparison: bool = False
    promote: bool = False


def _ensure():
    if not service.ready:
        raise ServiceUnavailable("Model not trained yet. Run `python scripts/train.py` or use the Federated Lab.")


def _when(r):
    try:
        v = pd.to_datetime(r.get("timestamp"), utc=True)
        return None if pd.isna(v) else v.tz_convert(None).to_pydatetime()
    except Exception:
        return None


def _persist(df: pd.DataFrame, results: list, source: str, truth=None, dataset_id=None):
    recs = []
    for i, (_, r) in enumerate(df.reset_index(drop=True).iterrows()):
        res = results[i]
        recs.append(dict(
            sender_id=str(r["sender_id"]) if "sender_id" in r and pd.notna(r["sender_id"]) and r["sender_id"] != "" else None,
            receiver_id=str(r["receiver_id"]) if "receiver_id" in r and pd.notna(r["receiver_id"]) and r["receiver_id"] != "" else None,
            txn_time=_when(r),
            txn_ref=str(r.get("transaction_id", f"API{i}")), source=source, bank=str(r.get("bank", "-")),
            category=str(r["merchant_category"]), amount=float(r["amount_inr"]), risk_score=res["risk_score"],
            risk_level=res["risk_level"], decision=res["decision"], reasons=res["reasons"],
            features={k: (v.item() if hasattr(v, "item") else v) for k, v in r.items() if k in REQUIRED + OPTIONAL},
            ground_truth=None if truth is None else int(truth[i]), dataset_id=dataset_id,
        ))
    return store.save(recs)


@public.get("/health")
def health():
    return {"status": "ok", "model_ready": service.ready, "model_version": MODEL_VERSION}


@router.get("/overview")
def overview():
    out = store.overview()
    report = json.loads(REPORT_PATH.read_text()) if REPORT_PATH.exists() else None
    out["model"] = None if not report else {
        "version": MODEL_VERSION, "metrics": report["final"]["metrics"], "trained_at": report["generated_at"],
        "banks": report["dataset"]["banks"], "dataset": report["dataset"].get("name", "upi"), "algorithm": report["config"]["algorithm"],
        "rounds": report["config"]["rounds"],
    }
    return out


@router.post("/transactions/score")
def score_one():
    _ensure()
    t = body(TxnIn)
    row = t.model_dump()
    now = store._utcnow()
    hist = store.history_counts(row["sender_id"], row["receiver_id"], now)
    row["transactions_last_hour"] = max(row["transactions_last_hour"], hist["last_hour"])
    row["sender_txn_24h"] = max(row["sender_txn_24h"], hist["last_24h"])
    row["same_receiver_24h"] = max(row["same_receiver_24h"], hist["same_receiver_24h"])
    if hist["minutes_since_last"] is not None:
        row["minutes_since_last_transaction"] = min(row["minutes_since_last_transaction"], hist["minutes_since_last"])
    row["timestamp"] = now.strftime("%Y-%m-%d %H:%M:%S")
    df = pd.DataFrame([row])
    res = service.score(df)
    saved = _persist(df, res, "api")
    return {**res[0], "id": saved[0]["id"]}


def _score_dataset(df: pd.DataFrame, dataset_id: int):
    _ensure()
    try:
        df = datasets.normalize_transactions(df)
        df = behavior.compute(df)       # repeat-payment features from sender_id / receiver_id / timestamp
        res = service.score(df, explain=True)
    except Exception as e:
        raise BadRequest(f"Invalid data: {e}") from e
    truth = None
    if "is_fraud" in df.columns:
        truth = pd.to_numeric(df["is_fraud"], errors="coerce").fillna(0).to_numpy()
    saved = _persist(df, res, "upload", truth, dataset_id)
    flagged = sum(1 for r in res if r["decision"] != "ALLOW")
    store.set_dataset_flagged(dataset_id, flagged)
    counts = pd.Series([r["decision"] for r in res]).value_counts().to_dict()
    return {"rows": len(df), "counts": counts, "flagged": flagged, "results": saved[:300]}


@router.post("/datasets")
def upload_dataset():
    """Store the uploaded file in the dataset library and score it immediately."""
    user = current_user()
    file = request.files.get("file")
    if file is None:
        raise UnprocessableEntity("Choose a file to upload.")
    raw = file.read(datasets.MAX_BYTES + 1)
    if len(raw) > datasets.MAX_BYTES:
        raise RequestEntityTooLarge("File larger than 300 MB.")
    try:
        df = datasets.parse(file.filename or "upload", raw)
    except Exception as e:
        raise BadRequest(f"Could not read file: {e}") from e
    stored = datasets.save_file(file.filename or "upload", raw)
    ds_id = store.add_dataset(user["id"], file.filename, stored, len(raw), len(df), list(df.columns))
    try:
        out = _score_dataset(df, ds_id)
    except Exception:
        datasets.remove_file(stored)
        store.delete_dataset(user["id"], ds_id)
        raise
    ds, _ = store.get_dataset(user["id"], ds_id)
    return {"dataset": ds, **out}


@router.get("/datasets")
def list_datasets():
    user = current_user()
    return store.list_datasets(user["id"])


@router.post("/datasets/<int:dataset_id>/rescore")
def rescore_dataset(dataset_id: int):
    user = current_user()
    ds, stored = store.get_dataset(user["id"], dataset_id)
    if not ds:
        raise NotFound("Dataset not found")
    store.delete_dataset_rows(dataset_id)
    return {"dataset": ds, **_score_dataset(datasets.parse(ds["filename"], datasets.load_file(stored)), dataset_id)}


@router.get("/datasets/<int:dataset_id>/file")
def download_original(dataset_id: int):
    user = current_user()
    ds, stored = store.get_dataset(user["id"], dataset_id)
    if not ds:
        raise NotFound("Dataset not found")
    return Response(datasets.load_file(stored), mimetype="application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="{ds["filename"]}"'})


@router.delete("/datasets/<int:dataset_id>")
def remove_dataset(dataset_id: int):
    user = current_user()
    stored = store.delete_dataset(user["id"], dataset_id)
    if stored is None:
        raise NotFound("Dataset not found")
    datasets.remove_file(stored)
    return {"deleted": True}


@router.get("/export/flagged")
def export_flagged():
    """Download detected fraud (flagged transactions) as csv / xlsx / docx / pdf / json."""
    format = request.args.get("format", "csv")
    dataset_id = integer_arg("dataset_id")
    decision = request.args.get("decision", "BLOCK,STEP_UP_AUTH")
    status = request.args.get("status")
    if format not in exports.FORMATS:
        raise BadRequest(f"Format must be one of {', '.join(exports.FORMATS)}")
    decisions = [d for d in decision.split(",") if d in {"BLOCK", "STEP_UP_AUTH", "ALLOW"}]
    rows = store.query_rows(decisions, status, dataset_id)
    if not rows:
        raise NotFound("No matching transactions to export.")
    data, media, name = exports.build(rows, format)
    return Response(data, mimetype=media, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/transactions")
def transactions():
    decision = request.args.get("decision")
    status = request.args.get("status")
    limit = integer_arg("limit") or 100
    offset = integer_arg("offset") or 0
    return store.listing(decision, status, min(max(limit, 1), 500), max(offset, 0))


class StatusIn(BaseModel):
    status: Literal["confirmed_fraud", "dismissed", "open"]


@router.patch("/transactions/<int:txn_id>")
def update_status(txn_id: int):
    row = store.set_status(txn_id, body(StatusIn).status)
    if not row:
        raise NotFound("Transaction not found")
    return row


@router.delete("/transactions")
def clear_history():
    store.clear()
    return {"cleared": True}


@router.get("/model/report")
def report():
    if not REPORT_PATH.exists():
        raise NotFound("No report yet. Run `python scripts/train.py`.")
    return json.loads(REPORT_PATH.read_text())


@router.get("/federated/status")
def fed_status():
    return training.status()


@router.post("/federated/train")
def fed_train():
    user = current_user()
    body_data = body(TrainIn)
    cfg = FedConfig(algorithm=body_data.algorithm, rounds=body_data.rounds, local_epochs=body_data.local_epochs, lr=body_data.lr,
                    mu=body_data.mu, dp_clip=body_data.dp_clip, dp_noise=body_data.dp_noise, secure_agg=body_data.secure_agg,
                    dp_delta=body_data.dp_delta)
    if not training.start(cfg, body_data.promote, body_data.full_comparison, user["id"]):
        raise Conflict("A training job is already running.")
    return {"started": True}


@router.get("/privacy/epsilon")
def privacy_epsilon():
    """Live epsilon preview for the Federated Lab."""
    from app.ml.privacy import epsilon
    try:
        noise = float(request.args["noise"])
        rounds = int(request.args["rounds"])
        delta = float(request.args.get("delta", 1e-5))
    except (KeyError, ValueError) as error:
        raise UnprocessableEntity("Provide valid noise, rounds and delta values.") from error
    e = epsilon(noise, rounds, delta)
    return {"epsilon": None if e == float("inf") else round(e, 2)}


@router.get("/papers")
def papers():
    return PAPERS

# End of API routes.

