"""REST API."""

import json
from typing import Literal

import pandas as pd
from flask import Blueprint, Response, request
from pydantic import BaseModel, Field, ValidationError
from werkzeug.exceptions import (
    BadRequest,
    Conflict,
    NotFound,
    RequestEntityTooLarge,
    ServiceUnavailable,
    UnprocessableEntity,
)

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
        raise UnprocessableEntity(
            "; ".join(item["msg"] for item in error.errors())
        ) from error


def integer_arg(name):
    value = request.args.get(name)
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError as error:
        raise UnprocessableEntity(f"{name} must be an integer.") from error


PAPERS = [
    {
        "title": "FedUPI: Federated Learning Empowered Detection of Fraudulent UPI Transactions",
        "authors": "Devassy et al.",
        "venue": "ICSCSA 2025",
        "url": "https://doi.org/10.1109/ICSCSA66339.2025.11170880",
        "used_for": "UPI-specific federated architecture and cross-institution collaboration.",
    },
    {
        "title": "Transparency and Privacy: Explainable AI and Federated Learning in Financial Fraud Detection",
        "authors": "Awosika, Shukla and Pranggono",
        "venue": "IEEE Access 2024",
        "url": "https://doi.org/10.1109/ACCESS.2024.3394528",
        "used_for": "Interpretability and privacy considerations for federated fraud models.",
    },
    {
        "title": "Secure UPI: Machine Learning-Driven Fraud Detection System for UPI Transactions",
        "authors": "Rani, Alam and Javed",
        "venue": "ICDT 2024",
        "url": "https://doi.org/10.1109/ICDT61202.2024.10489682",
        "used_for": "UPI transaction features and real-time alerting context.",
    },
    {
        "title": "Scalable Federated Learning for Privacy-Preserving Credit Card Fraud Detection",
        "authors": "D'Souza, Puthusseri and Samuel",
        "venue": "IEEE ICCST 2023",
        "url": "https://ieeexplore.ieee.org/document/10726848",
        "used_for": "Cross-institution fraud learning under class imbalance.",
    },
    {
        "title": (
            "Communication-Efficient Learning of Deep Networks from "
            "Decentralized Data (FedAvg)"
        ),
        "authors": "McMahan et al.",
        "venue": "AISTATS 2017",
        "url": "https://proceedings.mlr.press/v54/mcmahan17a.html",
        "used_for": "Core federated averaging used to combine bank models.",
    },
    {
        "title": "Federated Optimization in Heterogeneous Networks (FedProx)",
        "authors": "Li et al.",
        "venue": "MLSys 2020",
        "url": "https://arxiv.org/abs/1812.06127",
        "used_for": (
            "Proximal term that stabilises training when banks have "
            "different fraud patterns (non-IID)."
        ),
    },
    {
        "title": (
            "Practical Secure Aggregation for Privacy-Preserving "
            "Machine Learning"
        ),
        "authors": "Bonawitz et al.",
        "venue": "ACM CCS 2017",
        "url": "https://eprint.iacr.org/2017/281",
        "used_for": (
            "Pairwise-masked aggregation prototype; production still needs "
            "authenticated key exchange and dropout recovery."
        ),
    },
    {
        "title": "The Algorithmic Foundations of Differential Privacy",
        "authors": "Dwork and Roth",
        "venue": "Foundations and Trends in Theoretical Computer Science 2014",
        "url": "https://doi.org/10.1561/0400000042",
        "used_for": "Formal privacy framing and the optional differential-privacy extension.",
    },
    {
        "title": "A Unified Approach to Interpreting Model Predictions",
        "authors": "Lundberg and Lee",
        "venue": "NeurIPS 2017",
        "url": "https://proceedings.neurips.cc/paper/2017/hash/8a20a8621978632d76c43dfd28b67767-Abstract.html",
        "used_for": "Future explainability direction identified by the paper.",
    },
    {
        "title": "Flower: A Friendly Federated Learning Research Framework",
        "authors": "Beutel et al.",
        "venue": "arXiv 2020",
        "url": "https://arxiv.org/abs/2007.14390",
        "used_for": "Reference framework for a future multi-process deployment.",
    },
    {
        "title": "PaySim: A Financial Mobile Money Simulator for Fraud Detection",
        "authors": "Lopez-Rojas, Elmir and Axelsson",
        "venue": "EMSS 2016",
        "url": "https://github.com/EdgarLopezPhD/PaySim",
        "used_for": "Public simulation context and the optional PaySim data adapter.",
    },
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
    sender_id: str = Field(
        "", max_length=60
    )  # with receiver_id: repeat history is read from stored payments
    receiver_id: str = Field("", max_length=60)
    sender_txn_24h: int = Field(
        0, ge=0
    )  # manual override / extra known history
    same_receiver_24h: int = Field(0, ge=0)
    balance_drain: float = Field(
        0.0, ge=0, le=1
    )  # optional: amount / sender balance (PaySim model)
    dest_empty: Literal[0, 1] = (
        0  # optional: beneficiary account empty before payment
    )


class TrainIn(BaseModel):
    model: Literal["mlp", "paper_mlp"] = "mlp"
    algorithm: Literal["fedavg", "fedprox"] = "fedavg"
    rounds: int = Field(12, ge=1, le=40)
    local_epochs: int = Field(2, ge=1, le=5)
    lr: float = Field(0.01, gt=0, le=0.2)
    batch_size: int = Field(256, ge=32, le=2048)
    mu: float = Field(0.01, ge=0, le=1)
    dp_clip: float = Field(0.0, ge=0, le=10)
    dp_noise: float = Field(0.0, ge=0, le=5)
    secure_agg: bool = False
    dp_delta: float = Field(1e-5, gt=0, lt=1)
    full_comparison: bool = False
    promote: bool = False


def _ensure():
    if not service.ready:
        raise ServiceUnavailable(
            "Model not trained yet. Run `python scripts/train.py` or use "
            "the Federated Lab."
        )


def _when(r):
    try:
        v = pd.to_datetime(r.get("timestamp"), utc=True)
        return None if pd.isna(v) else v.tz_convert(None).to_pydatetime()
    except Exception:
        return None


def _persist(
    owner_id: int,
    df: pd.DataFrame,
    results: list,
    source: str,
    truth=None,
    dataset_id=None,
):
    recs = []
    for i, (_, r) in enumerate(df.reset_index(drop=True).iterrows()):
        res = results[i]
        recs.append(
            dict(
                sender_id=str(r["sender_id"])
                if "sender_id" in r
                and pd.notna(r["sender_id"])
                and r["sender_id"] != ""
                else None,
                receiver_id=str(r["receiver_id"])
                if "receiver_id" in r
                and pd.notna(r["receiver_id"])
                and r["receiver_id"] != ""
                else None,
                txn_time=_when(r),
                txn_ref=str(r.get("transaction_id", f"API{i}")),
                reference_id=(
                    str(r["reference_id"])
                    if "reference_id" in r and pd.notna(r["reference_id"]) and r["reference_id"] != ""
                    else None
                ),
                source=source,
                bank=str(r.get("bank", "-")),
                category=str(r["merchant_category"]),
                amount=float(r["amount_inr"]),
                risk_score=res["risk_score"],
                risk_level=res["risk_level"],
                decision=res["decision"],
                reasons=res["reasons"],
                model_version=res["model_version"],
                features={
                    k: (v.item() if hasattr(v, "item") else v)
                    for k, v in r.items()
                    if k in REQUIRED + OPTIONAL
                },
                ground_truth=None if truth is None else int(truth[i]),
                dataset_id=dataset_id,
            )
        )
    return store.save(owner_id, recs)


@public.get("/health")
def health():
    return {
        "status": "ok",
        "model_ready": service.ready,
        "model_version": MODEL_VERSION,
    }


@router.get("/overview")
def overview():
    user = current_user()
    out = store.overview(user["id"])
    report = (
        json.loads(REPORT_PATH.read_text()) if REPORT_PATH.exists() else None
    )
    out["model"] = (
        None
        if not report
        else {
            "version": MODEL_VERSION,
            "metrics": report["final"]["metrics"],
            "trained_at": report["generated_at"],
            "banks": report["dataset"]["banks"],
            "dataset": report["dataset"].get("name", "upi"),
            "algorithm": report["config"]["algorithm"],
            "rounds": report["config"]["rounds"],
        }
    )
    return out


@router.post("/transactions/score")
def score_one():
    _ensure()
    user = current_user()
    t = body(TxnIn)
    row = t.model_dump()
    now = store._utcnow()
    hist = store.history_counts(
        user["id"], row["sender_id"], row["receiver_id"], now
    )
    row["transactions_last_hour"] = max(
        row["transactions_last_hour"], hist["last_hour"]
    )
    row["sender_txn_24h"] = max(row["sender_txn_24h"], hist["last_24h"])
    row["same_receiver_24h"] = max(
        row["same_receiver_24h"], hist["same_receiver_24h"]
    )
    if hist["minutes_since_last"] is not None:
        row["minutes_since_last_transaction"] = min(
            row["minutes_since_last_transaction"], hist["minutes_since_last"]
        )
    row["timestamp"] = now.strftime("%Y-%m-%d %H:%M:%S")
    df = pd.DataFrame([row])
    res = service.score(df)
    saved = _persist(user["id"], df, res, "api")
    return {**res[0], "id": saved[0]["id"]}


def _score_dataset(owner_id: int, df: pd.DataFrame, dataset_id: int):
    _ensure()
    try:
        df = datasets.normalize_transactions(df)
        df = behavior.compute(
            df
        )  # repeat-payment features from sender_id / receiver_id / timestamp
        res = service.score(df, explain=True)
    except Exception as e:
        raise BadRequest(f"Invalid data: {e}") from e
    truth = None
    if "is_fraud" in df.columns:
        truth = (
            pd.to_numeric(df["is_fraud"], errors="coerce").fillna(0).to_numpy()
        )
    saved = _persist(owner_id, df, res, "upload", truth, dataset_id)
    flagged = sum(1 for r in res if r["decision"] != "ALLOW")
    store.set_dataset_flagged(dataset_id, flagged)
    counts = pd.Series([r["decision"] for r in res]).value_counts().to_dict()
    return {
        "rows": len(df),
        "counts": counts,
        "flagged": flagged,
        "results": saved[:300],
    }


@router.post("/datasets")
def upload_dataset():
    """Store an uploaded dataset and score it immediately."""
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
    ds_id = store.add_dataset(
        user["id"], file.filename, stored, len(raw), len(df), list(df.columns)
    )
    try:
        out = _score_dataset(user["id"], df, ds_id)
    except Exception:
        datasets.remove_file(stored)
        store.delete_dataset(user["id"], ds_id)
        raise
    # A successful upload becomes the owner's only active analysis. This is
    # intentionally after scoring so an invalid replacement cannot destroy
    # the user's current datasets, searches, alerts, or dashboard history.
    old_files = store.replace_owner_state_with_dataset(user["id"], ds_id)
    for old_file in old_files:
        datasets.remove_file(old_file)
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
    df = datasets.parse(ds["filename"], datasets.load_file(stored))
    return {"dataset": ds, **_score_dataset(user["id"], df, dataset_id)}


@router.get("/datasets/<int:dataset_id>/file")
def download_original(dataset_id: int):
    user = current_user()
    ds, stored = store.get_dataset(user["id"], dataset_id)
    if not ds:
        raise NotFound("Dataset not found")
    return Response(
        datasets.load_file(stored),
        mimetype="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{ds["filename"]}"'
        },
    )


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
    """Download flagged transactions in a supported format."""
    format = request.args.get("format", "csv")
    dataset_id = integer_arg("dataset_id")
    decision = request.args.get("decision", "BLOCK,STEP_UP_AUTH")
    status = request.args.get("status")
    if format not in exports.FORMATS:
        raise BadRequest(f"Format must be one of {', '.join(exports.FORMATS)}")
    decisions = [
        d
        for d in decision.split(",")
        if d in {"BLOCK", "STEP_UP_AUTH", "ALLOW"}
    ]
    user = current_user()
    rows = store.query_rows(user["id"], decisions, status, dataset_id)
    if not rows:
        raise NotFound("No matching transactions to export.")
    data, media, name = exports.build(rows, format)
    return Response(
        data,
        mimetype=media,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/transactions")
def transactions():
    user = current_user()
    decision = request.args.get("decision")
    status = request.args.get("status")
    limit = integer_arg("limit") or 100
    offset = integer_arg("offset") or 0
    dataset_id = integer_arg("dataset_id")
    if dataset_id:
        store.ensure_dataset_references(user["id"], dataset_id)
    return store.listing(
        user["id"], decision, status, dataset_id, min(max(limit, 1), 500), max(offset, 0)
    )


@router.get("/transactions/lookup")
def lookup_transaction():
    """Return a scored row by uploaded transaction ID, internal ID, or reference ID."""
    user = current_user()
    raw_id = (request.args.get("transaction_id") or "").strip()
    reference = (request.args.get("reference_id") or "").strip()
    if bool(raw_id) == bool(reference):
        raise BadRequest("Enter either a transaction ID or a reference ID.")
    row = None
    if raw_id:
        # Uploaded transaction IDs are stored verbatim in txn_ref and may be
        # alphanumeric. Prefer that exact value; retain the database row ID as
        # a fallback for the numeric IDs already shown elsewhere in the app.
        row = store.find_transaction(user["id"], transaction_identifier=raw_id)
        if not row and raw_id.isdigit() and int(raw_id) > 0:
            row = store.find_transaction(user["id"], txn_id=int(raw_id))
    else:
        store.ensure_all_dataset_references(user["id"])
        row = store.find_transaction(user["id"], reference=reference)
    if not row:
        raise NotFound("No transaction was found for that ID in your uploaded datasets or transaction history.")
    return row


class StatusIn(BaseModel):
    status: Literal["confirmed_fraud", "dismissed", "open"]


@router.patch("/transactions/<int:txn_id>")
def update_status(txn_id: int):
    user = current_user()
    row = store.set_status(user["id"], txn_id, body(StatusIn).status)
    if not row:
        raise NotFound("Transaction not found")
    return row


@router.delete("/transactions")
def clear_history():
    user = current_user()
    store.clear(user["id"])
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
    kind = "paper_mlp" if body_data.model == "paper_mlp" else "clf"
    cfg = FedConfig(
        kind=kind,
        algorithm=body_data.algorithm,
        rounds=body_data.rounds,
        local_epochs=body_data.local_epochs,
        lr=body_data.lr,
        batch_size=body_data.batch_size,
        mu=body_data.mu,
        dp_clip=body_data.dp_clip,
        dp_noise=body_data.dp_noise,
        secure_agg=body_data.secure_agg,
        dp_delta=body_data.dp_delta,
    )
    if not training.start(
        cfg, body_data.promote, body_data.full_comparison, user["id"]
    ):
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
        raise UnprocessableEntity(
            "Provide valid noise, rounds and delta values."
        ) from error
    e = epsilon(noise, rounds, delta)
    return {"epsilon": None if e == float("inf") else round(e, 2)}


@router.get("/papers")
def papers():
    return PAPERS


# End of API routes.
