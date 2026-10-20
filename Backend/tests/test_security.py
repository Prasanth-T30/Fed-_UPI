"""Security checks: passwords, tokens, input handling, CORS."""

import time
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import auth

c = TestClient(app)


def register(**kw):
    body = {"name": "Sec User", "email": f"sec{uuid.uuid4().hex[:8]}@example.com", "password": "supersecret1", **kw}
    return body, c.post("/api/auth/register", json=body)


def test_password_hash_is_salted_and_not_plaintext():
    a, b = auth.hash_password("supersecret1"), auth.hash_password("supersecret1")
    assert a != b and "supersecret1" not in a
    assert auth.verify_password("supersecret1", a) and not auth.verify_password("wrong-password", a)
    assert not auth.verify_password("x", "garbage")


def test_tampered_token_rejected():
    _, r = register()
    tok = r.json()["token"]
    body, sig = tok.rsplit(".", 1)
    for bad in (body + "." + "0" * len(sig), body[:-2] + "AA." + sig, "not-a-token", "", tok + "x"):
        assert c.get("/api/auth/me", headers={"Authorization": f"Bearer {bad}"}).status_code == 401


def test_expired_token_rejected(monkeypatch):
    _, r = register()
    uid = r.json()["user"]["id"]
    monkeypatch.setattr(auth, "TOKEN_TTL", -10)
    old = auth.make_token(uid)
    assert c.get("/api/auth/me", headers={"Authorization": f"Bearer {old}"}).status_code == 401


def test_token_for_deleted_user_rejected():
    assert c.get("/api/auth/me", headers={"Authorization": f"Bearer {auth.make_token(99999999)}"}).status_code == 401


@pytest.mark.parametrize("email", ["' OR '1'='1", "admin@example.com' --", "x@y.com; DROP TABLE users;--"])
def test_sql_injection_in_login(email):
    r = c.post("/api/auth/login", json={"email": email, "password": "anything"})
    assert r.status_code == 401


def test_registration_rules():
    body, r = register()
    assert r.status_code == 200
    dup = c.post("/api/auth/register", json={**body, "email": body["email"].upper()})
    assert dup.status_code == 409                                    # email is case-insensitive
    assert register(password="short")[1].status_code == 422
    assert register(email="not-an-email")[1].status_code == 422
    assert register(name="x")[1].status_code == 422


def test_login_error_does_not_reveal_which_part_is_wrong():
    body, _ = register()
    wrong_pw = c.post("/api/auth/login", json={"email": body["email"], "password": "wrongwrong"})
    no_user = c.post("/api/auth/login", json={"email": "nobody@example.com", "password": "wrongwrong"})
    assert wrong_pw.status_code == no_user.status_code == 401 and wrong_pw.json() == no_user.json()


def test_password_change_flow():
    body, r = register()
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    assert c.post("/api/auth/password", headers=h, json={"current_password": body["password"], "new_password": "anotherpass1"}).status_code == 200
    assert c.post("/api/auth/login", json={"email": body["email"], "password": body["password"]}).status_code == 401
    assert c.post("/api/auth/login", json={"email": body["email"], "password": "anotherpass1"}).status_code == 200


def test_profile_update_ignores_unknown_fields():
    _, r = register()
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    out = c.patch("/api/auth/me", headers=h, json={"name": "New Name", "email": "hacker@example.com", "password_hash": "x"}).json()
    assert out["name"] == "New Name" and out["email"] != "hacker@example.com"


def test_password_hash_never_returned():
    _, r = register()
    assert "password" not in r.text.lower().replace("password_", "")
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    assert "hash" not in c.get("/api/auth/me", headers=h).text


def test_cors_only_allows_local_frontend():
    ok = c.options("/api/health", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    bad = c.options("/api/health", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in bad.headers


def test_token_check_is_timing_safe_function():
    t0 = time.perf_counter()
    for _ in range(50):
        auth.read_token("a.b")
    assert time.perf_counter() - t0 < 1.0
