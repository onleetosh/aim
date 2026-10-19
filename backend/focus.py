# Work-session log (focus time), optionally tied to a task, plus the user's
# available-hours setting used to separate logged from unrecorded time.
from datetime import date, timedelta

from flask import Blueprint, jsonify, request

from .auth import login_required
from .database import get_connection
from .dates import parse_date, parse_int


focus_api = Blueprint("focus_api", __name__)

MAX_MINUTES_PER_ENTRY = 24 * 60
DEFAULT_AVAILABLE_MINUTES = 480
ENTRY_SELECT = """
    SELECT work_sessions.id, work_sessions.entry_date, work_sessions.minutes,
           work_sessions.note, work_sessions.task_id, tasks.title AS task_title
    FROM work_sessions
    LEFT JOIN tasks ON tasks.id = work_sessions.task_id
"""


def entry_from_row(row):
    return {
        "id": row["id"],
        "date": str(row["entry_date"]),
        "minutes": row["minutes"],
        "note": row["note"],
        "taskId": str(row["task_id"]) if row["task_id"] is not None else None,
        "taskTitle": row["task_title"],
    }


def read_available_minutes(connection, user_id):
    row = connection.execute(
        "SELECT available_minutes_per_day FROM user_settings WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    return row["available_minutes_per_day"] if row else DEFAULT_AVAILABLE_MINUTES


@focus_api.get("/api/focus")
@login_required
def get_focus(user):
    days = max(1, min(parse_int(request.args.get("days")) or 30, 366))
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    with get_connection() as connection:
        rows = connection.execute(
            ENTRY_SELECT
            + " WHERE work_sessions.user_id = ? AND work_sessions.entry_date >= ?"
            " ORDER BY work_sessions.entry_date DESC, work_sessions.id DESC",
            (user["id"], since),
        ).fetchall()
        return jsonify({"entries": [entry_from_row(row) for row in rows]})


@focus_api.post("/api/focus/entries")
@login_required
def create_entry(user):
    data = request.get_json(silent=True) or {}
    entry_date = parse_date(data.get("date"))
    minutes = parse_int(data.get("minutes"))
    note = str(data.get("note", "")).strip()[:300]
    raw_task = data.get("taskId")
    task_id = parse_int(raw_task) if raw_task not in (None, "") else None
    if entry_date is None:
        return jsonify({"error": "A valid date is required."}), 400
    if minutes is None or not 1 <= minutes <= MAX_MINUTES_PER_ENTRY:
        return jsonify({"error": "Minutes must be between 1 and 1440."}), 400
    if raw_task not in (None, "") and task_id is None:
        return jsonify({"error": "The selected task does not exist."}), 400

    with get_connection() as connection:
        if task_id is not None:
            owned = connection.execute(
                "SELECT tasks.id FROM tasks JOIN projects ON projects.id = tasks.project_id "
                "WHERE tasks.id = ? AND projects.user_id = ?",
                (task_id, user["id"]),
            ).fetchone()
            if owned is None:
                return jsonify({"error": "The selected task does not exist."}), 400
            # Working on a task counts as progress for stale-work detection.
            connection.execute(
                "UPDATE tasks SET updated_on = ? WHERE id = ? AND (updated_on IS NULL OR updated_on < ?)",
                (entry_date, task_id, entry_date),
            )
        cursor = connection.execute(
            "INSERT INTO work_sessions (user_id, task_id, entry_date, minutes, note) "
            "VALUES (?, ?, ?, ?, ?)",
            (user["id"], task_id, entry_date, minutes, note),
        )
        row = connection.execute(
            ENTRY_SELECT + " WHERE work_sessions.id = ?", (cursor.lastrowid,)
        ).fetchone()
        return jsonify(entry_from_row(row)), 201


@focus_api.delete("/api/focus/entries/<int:entry_id>")
@login_required
def delete_entry(user, entry_id):
    with get_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM work_sessions WHERE id = ? AND user_id = ?",
            (entry_id, user["id"]),
        )
        if cursor.rowcount == 0:
            return jsonify({"error": "Entry not found."}), 404
    return ("", 204)


@focus_api.get("/api/settings")
@login_required
def get_settings(user):
    with get_connection() as connection:
        return jsonify({"availableMinutesPerDay": read_available_minutes(connection, user["id"])})


@focus_api.put("/api/settings")
@login_required
def update_settings(user):
    data = request.get_json(silent=True) or {}
    minutes = parse_int(data.get("availableMinutesPerDay"))
    if minutes is None or not 30 <= minutes <= MAX_MINUTES_PER_ENTRY:
        return jsonify({"error": "Available time must be between 30 and 1440 minutes."}), 400
    with get_connection() as connection:
        cursor = connection.execute(
            "UPDATE user_settings SET available_minutes_per_day = ? WHERE user_id = ?",
            (minutes, user["id"]),
        )
        if cursor.rowcount == 0:
            connection.execute(
                "INSERT INTO user_settings (user_id, available_minutes_per_day) VALUES (?, ?)",
                (user["id"], minutes),
            )
        return jsonify({"availableMinutesPerDay": minutes})
