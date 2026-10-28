# Downtime log: manual entries recording time lost, with a reason.
from datetime import date, timedelta

from flask import Blueprint, jsonify, request

from .auth import login_required
from .database import get_connection
from .dates import parse_date, parse_int

downtime_api = Blueprint("downtime_api", __name__)

MAX_MINUTES_PER_ENTRY = 24 * 60
ENTRY_COLUMNS = "id, entry_date, minutes, reason, note"


def entry_from_row(row):
    return {
        "id": row["id"],
        "date": str(row["entry_date"]),
        "minutes": row["minutes"],
        "reason": row["reason"],
        "note": row["note"],
    }


@downtime_api.get("/api/downtime")
@login_required
def get_downtime(user):
    days = parse_int(request.args.get("days")) or 30
    days = max(1, min(days, 366))
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    with get_connection() as connection:
        rows = connection.execute(
            f"SELECT {ENTRY_COLUMNS} FROM downtime_entries "
            "WHERE user_id = ? AND entry_date >= ? ORDER BY entry_date DESC, id DESC",
            (user["id"], since),
        ).fetchall()
        return jsonify({"entries": [entry_from_row(row) for row in rows]})


@downtime_api.post("/api/downtime/entries")
@login_required
def create_entry(user):
    data = request.get_json(silent=True) or {}
    entry_date = parse_date(data.get("date"))
    minutes = parse_int(data.get("minutes"))
    reason = str(data.get("reason", "")).strip()[:60]
    note = str(data.get("note", "")).strip()[:300]
    if entry_date is None:
        return jsonify({"error": "A valid date is required."}), 400
    if minutes is None or not 1 <= minutes <= MAX_MINUTES_PER_ENTRY:
        return jsonify({"error": "Minutes must be between 1 and 1440."}), 400

    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO downtime_entries (user_id, entry_date, minutes, reason, note) "
            "VALUES (?, ?, ?, ?, ?) RETURNING id",
            (user["id"], entry_date, minutes, reason, note),
        )
        row = connection.execute(
            f"SELECT {ENTRY_COLUMNS} FROM downtime_entries WHERE id = ?",
            (cursor.fetchone()["id"],),
        ).fetchone()
        return jsonify(entry_from_row(row)), 201


@downtime_api.delete("/api/downtime/entries/<int:entry_id>")
@login_required
def delete_entry(user, entry_id):
    with get_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM downtime_entries WHERE id = ? AND user_id = ?",
            (entry_id, user["id"]),
        )
        if cursor.rowcount == 0:
            return jsonify({"error": "Entry not found."}), 404
    return ("", 204)
