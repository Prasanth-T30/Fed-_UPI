"""Authentication: scrypt password hashes + HMAC-signed bearer tokens (stdlib only)."""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from flask import request
from werkzeug.exceptions import Unauthorized

from app.config import ROOT
from app.services import store

TOKEN_TTL = 60 * 60 * 12
_KEY_FILE = ROOT / "storage" / "secret.key"


def _secret() -> bytes:
    env = os.environ.get("FEDUPI_SECRET")
    if env:
        return env.encode()
    _KEY_FILE.parent.mkdir(exist_ok=True)
    if not _KEY_FILE.exists():
        _KEY_FILE.write_text(secrets.token_hex(32))
    return _KEY_FILE.read_text().encode()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(password.encode(), salt=salt, n=2 ** 14, r=8, p=1)
    return f"{salt.hex()}${h.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, h = stored.split("$")
        calc = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2 ** 14, r=8, p=1)
        return hmac.compare_digest(calc.hex(), h)
    except Exception:
        return False


def make_token(user_id: int) -> str:
    body = base64.urlsafe_b64encode(json.dumps({"uid": user_id, "exp": int(time.time()) + TOKEN_TTL}).encode()).decode()
    sig = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def read_token(token: str):
    try:
        body, sig = token.rsplit(".", 1)
        good = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, good):
            return None
        data = json.loads(base64.urlsafe_b64decode(body.encode()))
        return data["uid"] if data["exp"] > time.time() else None
    except Exception:
        return None


def current_user() -> dict:
    authorization = request.headers.get("Authorization", "")
    token = authorization.removeprefix("Bearer ").strip()
    uid = read_token(token) if token else None
    user = store.get_user(uid) if uid else None
    if not user:
        raise Unauthorized("Not authenticated")
    return user
