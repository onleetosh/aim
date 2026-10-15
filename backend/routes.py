# HTTP routes for the page and the project/task JSON API.
# Every API route is scoped to the logged-in user's own projects.
from flask import Blueprint, jsonify, render_template, request

from .auth import current_user, login_required
from .database import get_connection
from .serializers import project_from_row, state_response, task_from_row


api = Blueprint("api", __name__)

OWNED_PROJECTS = "SELECT id FROM projects WHERE user_id = ?"


@api.get("/")
def index():
    user = current_user()
    return render_template("index.html", username=user["username"] if user else None)


@api.get("/api/state")
@login_required
def get_state(user):
    with get_connection() as connection:
        return jsonify(state_response(connection, user["id"]))


@api.post("/api/projects")
@login_required
def create_project(user):
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    description = str(data.get("description", "")).strip()
    if not title:
        return jsonify({"error": "Project title is required."}), 400

    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO projects (title, description, user_id) VALUES (?, ?, ?)",
            (title, description, user["id"]),
        )
        row = connection.execute(
            "SELECT id, title, description FROM projects WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        return jsonify(project_from_row(row)), 201


@api.delete("/api/projects/<int:project_id>")
@login_required
def delete_project(user, project_id):
    with get_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM projects WHERE id = ? AND user_id = ?",
            (project_id, user["id"]),
        )
        if cursor.rowcount == 0:
            return jsonify({"error": "Project not found."}), 404
    return ("", 204)


@api.post("/api/tasks")
@login_required
def create_task(user):
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    description = str(data.get("description", "")).strip()
    project_id = data.get("projectId")
    if not title or not project_id:
        return jsonify({"error": "Task title and project are required."}), 400

    with get_connection() as connection:
        project = connection.execute(
            "SELECT id FROM projects WHERE id = ? AND user_id = ?",
            (project_id, user["id"]),
        ).fetchone()
        if project is None:
            return jsonify({"error": "The selected project does not exist."}), 400
        cursor = connection.execute(
            """
            INSERT INTO tasks (project_id, title, description)
            VALUES (?, ?, ?)
            """,
            (project_id, title, description),
        )
        row = connection.execute(
            """
            SELECT id, project_id, title, description, status
            FROM tasks WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()
        return jsonify(task_from_row(row)), 201


@api.patch("/api/tasks/<int:task_id>")
@login_required
def update_task(user, task_id):
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    allowed_statuses = {"new", "ready", "progress", "review", "done"}
    if status not in allowed_statuses:
        return jsonify({"error": "Invalid task status."}), 400

    with get_connection() as connection:
        cursor = connection.execute(
            f"UPDATE tasks SET status = ? WHERE id = ? AND project_id IN ({OWNED_PROJECTS})",
            (status, task_id, user["id"]),
        )
        if cursor.rowcount == 0:
            return jsonify({"error": "Task not found."}), 404
        row = connection.execute(
            """
            SELECT id, project_id, title, description, status
            FROM tasks WHERE id = ?
            """,
            (task_id,),
        ).fetchone()
        return jsonify(task_from_row(row))


@api.delete("/api/tasks/<int:task_id>")
@login_required
def delete_task(user, task_id):
    with get_connection() as connection:
        cursor = connection.execute(
            f"DELETE FROM tasks WHERE id = ? AND project_id IN ({OWNED_PROJECTS})",
            (task_id, user["id"]),
        )
        if cursor.rowcount == 0:
            return jsonify({"error": "Task not found."}), 404
    return ("", 204)
