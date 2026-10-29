import io
import uuid

import pandas as pd
import pytest
from flask_client import TestClient

from app.data.generator import generate
from app.main import app
from app.services.scoring import service

c = TestClient(app)


@pytest.fixture(scope="module")
def auth():
    email = f"t{uuid.uuid4().hex[:8]}@example.com"
    r = c.post("/api/auth/register", json={"name": "Test User", "email": email, "password": "supersecret1"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}, email


def test_auth_flow(auth):
    h, email = auth
    assert c.get("/api/overview").status_code == 401
    assert c.get("/api/auth/me", headers=h).json()["email"] == email
    assert c.post("/api/auth/login", json={"email": email, "password": "wrongwrong"}).status_code == 401
    ok = c.post("/api/auth/login", json={"email": email, "password": "supersecret1"})
    assert ok.status_code == 200
    assert c.post("/api/auth/register", json={"name": "Dup", "email": email, "password": "supersecret1"}).status_code == 409
    up = c.patch("/api/auth/me", headers=h, json={"organization": "Acme Bank"}).json()
    assert up["organization"] == "Acme Bank"
    assert c.post("/api/auth/password", headers=h, json={"current_password": "bad", "new_password": "newpassword1"}).status_code == 400


def test_score_endpoint(auth):
    if not service.ready:
        pytest.skip("model not trained")
    h, _ = auth
    ok = c.post("/api/transactions/score", headers=h, json={"amount_inr": 500, "merchant_category": "merchant"})
    assert ok.status_code == 200 and ok.json()["decision"] in {"ALLOW", "STEP_UP_AUTH", "BLOCK"}
    assert c.post("/api/transactions/score", headers=h, json={"amount_inr": -5}).status_code == 422
    scam = c.post("/api/transactions/score", headers=h, json={
        "amount_inr": 40000, "amount_to_average_ratio": 6, "is_new_device": 1, "is_new_beneficiary": 1,
        "failed_login_attempts_24h": 4, "transaction_hour": 3}).json()
    assert scam["risk_score"] > ok.json()["risk_score"] and scam["reasons"]


def test_upload_export_roundtrip(auth):
    if not service.ready:
        pytest.skip("model not trained")
    h, _ = auth
    df = generate(seed=5, scale=0.04).head(300)
    xl = io.BytesIO()
    df.to_excel(xl, index=False)
    r = c.post("/api/datasets", headers=h, files={"file": ("sample.xlsx", xl.getvalue())})
    assert r.status_code == 200, r.text
    ds = r.json()["dataset"]
    assert ds["rows"] == 300 and len(c.get("/api/datasets", headers=h).json()) >= 1
    filtered = c.get(f"/api/transactions?dataset_id={ds['id']}&limit=500", headers=h).json()
    assert len(filtered) == 300 and all(row["dataset_id"] == ds["id"] for row in filtered)
    for fmt, magic in (("csv", b""), ("xlsx", b"PK"), ("docx", b"PK"), ("pdf", b"%PDF"), ("json", b"[")):
        e = c.get(f"/api/export/flagged?format={fmt}&dataset_id={ds['id']}", headers=h)
        assert e.status_code == 200 and e.content.startswith(magic), fmt
    assert c.get("/api/export/flagged?format=exe", headers=h).status_code == 400
    flexible = c.post("/api/datasets", headers=h, files={"file": ("x.csv", b"a,b\n1,2\n")})
    assert flexible.status_code == 200
    assert c.delete(f"/api/datasets/{flexible.json()['dataset']['id']}", headers=h).status_code == 200
    assert c.delete(f"/api/datasets/{ds['id']}", headers=h).status_code == 200


def test_policy_rules_demo_upload(auth):
    """70,000-99,999 -> MODERATE, >=100,000 -> HIGH, repeats flagged, 5 earlier-payment burst flagged, small normal stays LOW."""
    if not service.ready:
        pytest.skip("model not trained")
    h, _ = auth
    path = __import__("pathlib").Path(__file__).resolve().parents[2] / "samples" / "policy_rules_demo.csv"
    r = c.post("/api/datasets", headers=h, files={"file": ("policy_rules_demo.csv", path.read_bytes())})
    assert r.status_code == 200, r.text
    rows = {x["txn_ref"]: x for x in r.json()["results"]}
    demo = pd.read_csv(path).set_index("transaction_id")
    def level(amount):
        return next(
            rows[i]["decision"]
            for i in demo.index
            if demo.loc[i, "amount_inr"] == amount and demo.loc[i, "sender_id"].startswith("A-BAND")
        )

    assert level(500) == "ALLOW" and level(69_999) == "ALLOW"
    assert level(70_000) == "STEP_UP_AUTH" and level(99_999) == "STEP_UP_AUTH"
    assert level(100_000) == "BLOCK" and level(199_000) == "BLOCK"
    repeat = [rows[i] for i in demo.index if demo.loc[i, "sender_id"] == "A-REPEAT1"]
    assert all(x["decision"] != "BLOCK" for x in repeat) and repeat[-1]["decision"] == "STEP_UP_AUTH"
    assert any("same receiver" in (y["reason"]) for y in repeat[-1]["reasons"])
    assert all(0 <= x["risk_score"] <= 99.9 for x in rows.values())
    friend = [rows[i] for i in demo.index if demo.loc[i, "sender_id"] == "A-FRIEND"]
    assert friend[-1]["decision"] == "ALLOW"
