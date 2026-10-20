"""SQLite persistence for scored transactions and the analyst alert queue."""

import datetime as dt
import json

from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, create_engine, func, select
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import DB_URL

def _utcnow():
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)   # naive UTC, as stored


Base = declarative_base()
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
Session = sessionmaker(engine, expire_on_commit=False)


class Txn(Base):
    __tablename__ = "scored_transactions"
    id = Column(Integer, primary_key=True)
    txn_ref = Column(String, index=True)
    created_at = Column(DateTime, default=_utcnow, index=True)
    source = Column(String, default="api")           # api | upload | simulation
    bank = Column(String, default="-")
    category = Column(String)
    amount = Column(Float)
    risk_score = Column(Float)
    risk_level = Column(String, index=True)
    decision = Column(String, index=True)
    reasons = Column(JSON)
    features = Column(JSON)
    ground_truth = Column(Integer, nullable=True)     # only known for simulated data
    status = Column(String, default="open", index=True)  # open | confirmed_fraud | dismissed | auto
    dataset_id = Column(Integer, nullable=True, index=True)
    sender_id = Column(String, nullable=True, index=True)
    receiver_id = Column(String, nullable=True)
    txn_time = Column(DateTime, nullable=True, index=True)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    organization = Column(String, default="")
    role = Column(String, default="Fraud analyst")
    password_hash = Column(String)
    created_at = Column(DateTime, default=_utcnow)


class Dataset(Base):
    __tablename__ = "datasets"
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, index=True)
    filename = Column(String)
    stored_as = Column(String)
    size_bytes = Column(Integer)
    rows = Column(Integer)
    columns = Column(JSON)
    flagged = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)


Base.metadata.create_all(engine)


def _migrate():
    """create_all never alters tables; add columns introduced after the first release."""
    from sqlalchemy import inspect, text
    cols = {c["name"] for c in inspect(engine).get_columns("scored_transactions")}
    for name, typ in (("dataset_id", "INTEGER"), ("sender_id", "VARCHAR"), ("receiver_id", "VARCHAR"), ("txn_time", "DATETIME")):
        if name not in cols:
            with engine.begin() as c:
                c.execute(text(f"ALTER TABLE scored_transactions ADD COLUMN {name} {typ}"))


_migrate()


def user_dict(u: User) -> dict:
    return {"id": u.id, "email": u.email, "name": u.name, "organization": u.organization, "role": u.role,
            "created_at": u.created_at.isoformat() + "Z"}


def get_user(uid):
    with Session() as s:
        u = s.get(User, uid)
        return user_dict(u) if u else None


def find_user(email: str):
    with Session() as s:
        return s.execute(select(User).where(User.email == email.lower().strip())).scalar_one_or_none()


def create_user(email, name, password_hash, organization="", role="Fraud analyst"):
    with Session() as s:
        u = User(email=email.lower().strip(), name=name.strip(), password_hash=password_hash,
                 organization=organization, role=role)
        s.add(u); s.commit()
        return user_dict(u)


def update_user(uid, **fields):
    with Session() as s:
        u = s.get(User, uid)
        for k, v in fields.items():
            if v is not None:
                setattr(u, k, v)
        s.commit()
        return user_dict(u)


def password_hash_of(uid):
    with Session() as s:
        return s.get(User, uid).password_hash


def dataset_dict(d: Dataset) -> dict:
    return {"id": d.id, "filename": d.filename, "size_bytes": d.size_bytes, "rows": d.rows, "columns": d.columns,
            "flagged": d.flagged, "created_at": d.created_at.isoformat() + "Z"}


def add_dataset(owner_id, filename, stored_as, size, rows, columns):
    with Session() as s:
        d = Dataset(owner_id=owner_id, filename=filename, stored_as=stored_as, size_bytes=size, rows=rows, columns=columns)
        s.add(d); s.commit()
        return d.id


def list_datasets(owner_id):
    with Session() as s:
        rows = s.execute(select(Dataset).where(Dataset.owner_id == owner_id).order_by(Dataset.id.desc())).scalars().all()
        return [dataset_dict(d) for d in rows]


def get_dataset(owner_id, dataset_id):
    with Session() as s:
        d = s.get(Dataset, dataset_id)
        return (dataset_dict(d), d.stored_as) if d and d.owner_id == owner_id else (None, None)


def set_dataset_flagged(dataset_id, n):
    with Session() as s:
        s.get(Dataset, dataset_id).flagged = n
        s.commit()


def delete_dataset(owner_id, dataset_id):
    with Session() as s:
        d = s.get(Dataset, dataset_id)
        if not d or d.owner_id != owner_id:
            return None
        stored = d.stored_as
        s.query(Txn).filter(Txn.dataset_id == dataset_id).delete()
        s.delete(d); s.commit()
        return stored


def query_rows(decisions=None, status=None, dataset_id=None, limit=20000):
    with Session() as s:
        q = select(Txn).order_by(Txn.id.desc())
        if decisions:
            q = q.where(Txn.decision.in_(decisions))
        if status:
            q = q.where(Txn.status == status)
        if dataset_id:
            q = q.where(Txn.dataset_id == dataset_id)
        return [row_dict(r) for r in s.execute(q.limit(limit)).scalars().all()]


def row_dict(t: Txn) -> dict:
    return {
        "id": t.id, "txn_ref": t.txn_ref, "created_at": t.created_at.isoformat() + "Z", "source": t.source,
        "bank": t.bank, "category": t.category, "amount": t.amount, "risk_score": t.risk_score,
        "risk_level": t.risk_level, "decision": t.decision, "reasons": t.reasons or [],
        "features": t.features, "ground_truth": t.ground_truth, "status": t.status, "dataset_id": t.dataset_id,
        "sender_id": t.sender_id, "receiver_id": t.receiver_id,
        "txn_time": t.txn_time.isoformat() if t.txn_time else None,
    }


def save(records: list) -> list:
    with Session() as s:
        objs = []
        for r in records:
            status = "open" if r["decision"] != "ALLOW" else "auto"
            objs.append(Txn(status=status, **r))
        s.add_all(objs)
        s.commit()
        return [row_dict(o) for o in objs]


def overview() -> dict:
    with Session() as s:
        total = s.scalar(select(func.count(Txn.id))) or 0
        by_dec = dict(s.execute(select(Txn.decision, func.count(Txn.id)).group_by(Txn.decision)).all())
        blocked_amt = s.scalar(select(func.coalesce(func.sum(Txn.amount), 0)).where(Txn.decision == "BLOCK")) or 0
        open_alerts = s.scalar(select(func.count(Txn.id)).where(Txn.status == "open")) or 0
        confirmed = s.scalar(select(func.count(Txn.id)).where(Txn.status == "confirmed_fraud")) or 0
        recent = s.execute(select(Txn).order_by(Txn.id.desc()).limit(60)).scalars().all()
        sim = s.execute(select(Txn).where(Txn.ground_truth.is_not(None))).scalars().all()
    tp = sum(1 for t in sim if t.ground_truth == 1 and t.decision != "ALLOW")
    fn = sum(1 for t in sim if t.ground_truth == 1 and t.decision == "ALLOW")
    fp = sum(1 for t in sim if t.ground_truth == 0 and t.decision != "ALLOW")
    return {
        "total": total, "blocked": by_dec.get("BLOCK", 0), "step_up": by_dec.get("STEP_UP_AUTH", 0),
        "allowed": by_dec.get("ALLOW", 0), "blocked_amount": round(float(blocked_amt), 2),
        "open_alerts": open_alerts, "confirmed_fraud": confirmed,
        "live_accuracy": {"caught": tp, "missed": fn, "false_alarms": fp},
        "recent": [{"id": t.id, "risk_score": t.risk_score, "decision": t.decision, "amount": t.amount,
                    "created_at": t.created_at.isoformat() + "Z"} for t in reversed(recent)],
    }


def listing(decision=None, status=None, limit=100, offset=0):
    with Session() as s:
        q = select(Txn).order_by(Txn.id.desc())
        if decision:
            q = q.where(Txn.decision == decision)
        if status:
            q = q.where(Txn.status == status)
        rows = s.execute(q.limit(limit).offset(offset)).scalars().all()
        return [row_dict(r) for r in rows]


def set_status(txn_id: int, status: str):
    with Session() as s:
        t = s.get(Txn, txn_id)
        if not t:
            return None
        t.status = status
        s.commit()
        return row_dict(t)


def clear():
    with Session() as s:
        s.query(Txn).delete()
        s.commit()


def delete_dataset_rows(dataset_id):
    with Session() as s:
        s.query(Txn).filter(Txn.dataset_id == dataset_id).delete()
        s.commit()


def history_counts(sender_id, receiver_id, at):
    """Prior payments (stored in the database) by this sender: last hour, last 24h, and to this receiver in 24h."""
    if not sender_id:
        return {"last_hour": 0, "last_24h": 0, "same_receiver_24h": 0, "minutes_since_last": None}
    day, hour = at - dt.timedelta(hours=24), at - dt.timedelta(hours=1)
    with Session() as s:
        base = select(func.count(Txn.id)).where(Txn.sender_id == sender_id, Txn.txn_time < at)
        last_day = s.scalar(base.where(Txn.txn_time >= day)) or 0
        last_hour = s.scalar(base.where(Txn.txn_time >= hour)) or 0
        same = s.scalar(base.where(Txn.txn_time >= day, Txn.receiver_id == receiver_id)) if receiver_id else 0
        prev = s.scalar(select(func.max(Txn.txn_time)).where(Txn.sender_id == sender_id, Txn.txn_time < at))
    mins = round((at - prev).total_seconds() / 60, 1) if prev else None
    return {"last_hour": last_hour, "last_24h": last_day, "same_receiver_24h": same or 0, "minutes_since_last": mins}
