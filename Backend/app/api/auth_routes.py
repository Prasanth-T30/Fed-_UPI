"""Registration, login and profile endpoints."""

import re

from flask import Blueprint, request
from pydantic import BaseModel, Field, ValidationError
from werkzeug.exceptions import BadRequest, Conflict, Unauthorized, UnprocessableEntity

from app.services import auth, store

router = Blueprint("auth", __name__, url_prefix="/api/auth")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(max_length=120)
    password: str = Field(min_length=8, max_length=128)
    organization: str = Field("", max_length=120)


class LoginIn(BaseModel):
    email: str
    password: str


class ProfileIn(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=80)
    organization: str | None = Field(None, max_length=120)
    role: str | None = Field(None, max_length=60)


class PasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


def body(model):
    try:
        return model.model_validate(request.get_json(silent=True) or {})
    except ValidationError as error:
        raise UnprocessableEntity("; ".join(item["msg"] for item in error.errors())) from error


@router.post("/register")
def register():
    b = body(RegisterIn)
    if not EMAIL.match(b.email):
        raise UnprocessableEntity("Enter a valid email address.")
    if store.find_user(b.email):
        raise Conflict("An account with this email already exists.")
    user = store.create_user(b.email, b.name, auth.hash_password(b.password), b.organization)
    return {"token": auth.make_token(user["id"]), "user": user}


@router.post("/login")
def login():
    b = body(LoginIn)
    u = store.find_user(b.email)
    if not u or not auth.verify_password(b.password, u.password_hash):
        raise Unauthorized("Incorrect email or password.")
    return {"token": auth.make_token(u.id), "user": store.user_dict(u)}


@router.get("/me")
def me():
    return auth.current_user()


@router.patch("/me")
def update_me():
    user = auth.current_user()
    b = body(ProfileIn)
    return store.update_user(user["id"], **b.model_dump())


@router.post("/password")
def change_password():
    user = auth.current_user()
    b = body(PasswordIn)
    if not auth.verify_password(b.current_password, store.password_hash_of(user["id"])):
        raise BadRequest("Current password is incorrect.")
    store.update_user(user["id"], password_hash=auth.hash_password(b.new_password))
    return {"changed": True}
