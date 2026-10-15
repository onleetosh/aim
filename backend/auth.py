# Account registration, login, and session helpers.
import re
from functools import wraps

from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from .database import get_connection, integrity_errors


auth = Blueprint("auth", __name__, url_prefix="/api/auth")

USERNAME_PATTERN = re.compile(r"^[a-z0-9_.-]{3,30}$")
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
# Checked when a username does not exist so response time doesn't reveal it.
DUMMY_HASH = generate_password_hash("not-a-real-password")


def current_user():
    user_id = session.get("user_id")
    if user_id is None:
        return None
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, username FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    if row is None:
        session.clear()
        return None
    return {"id": row["id"], "username": row["username"]}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            return jsonify({"error": "Please log in to continue."}), 401
        return view(user, *args, **kwargs)

    return wrapped


def start_session(user_id):
    session.clear()
    session["user_id"] = user_id
    session.permanent = True


def credentials_from_request():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip().lower()
    password = str(data.get("password", ""))
    return username, password


@auth.post("/register")
def register():
    username, password = credentials_from_request()
    if not USERNAME_PATTERN.match(username):
        return jsonify({
            "error": "Username must be 3-30 characters: letters, numbers, dots, dashes or underscores."
        }), 400
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        return jsonify({
            "error": f"Password must be {MIN_PASSWORD_LENGTH}-{MAX_PASSWORD_LENGTH} characters."
        }), 400

    try:
        with get_connection() as connection:
            cursor = connection.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, generate_password_hash(password)),
            )
            user_id = cursor.lastrowid
    except integrity_errors():
        return jsonify({"error": "That username is already taken."}), 409

    start_session(user_id)
    return jsonify({"id": user_id, "username": username}), 201


@auth.post("/login")
def login():
    username, password = credentials_from_request()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    password_hash = row["password_hash"] if row else DUMMY_HASH
    valid = check_password_hash(password_hash, password)
    if row is None or not valid:
        return jsonify({"error": "Incorrect username or password."}), 401

    start_session(row["id"])
    return jsonify({"id": row["id"], "username": row["username"]})


@auth.post("/logout")
def logout():
    session.clear()
    return ("", 204)
