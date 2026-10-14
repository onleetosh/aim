# HTTP routes for the page and the project/task JSON API.
from flask import Blueprint, jsonify, render_template, request

from .database import get_connection
from .serializers import project_from_row, state_response, task_from_row


api = Blueprint("api", __name__)


@api.get("/")
def index():
    return render_template("index.html")


@api.get("/api/state")
def get_state():
    with get_connection() as connection:
        return jsonify(state_response(connection))


@api.post("/api/projects")
def create_project():
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    description = str(data.get("description", "")).strip()
    if not title:
        return jsonify({"error": "Project title is required."}), 400

    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO projects (title, description) VALUES (?, ?)",
            (title, description),
        )
        row = connection.execute(
            "SELECT id, title, description FROM projects WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        return jsonify(project_from_row(row)), 201


@api.delete("/api/projects/<int:project_id>")
def delete_project(project_id):
    with get_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM projects WHERE id = ?", (project_id,)
        )
        if cursor.rowcount == 0:
            return jsonify({"error": "Project not found."}), 404
    return ("", 204)


@api.post("/api/tasks")
def create_task():
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    description = str(data.get("description", "")).strip()
    project_id = data.get("projectId")
    if not title or not project_id:
        return jsonify({"error": "Task title and project are required."}), 400

    with get_connection() as connection:
        project = connection.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
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
def update_task(task_id):
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    allowed_statuses = {"new", "ready", "progress", "review", "done"}
    if status not in allowed_statuses:
        return jsonify({"error": "Invalid task status."}), 400

    with get_connection() as connection:
        cursor = connection.execute(
            "UPDATE tasks SET status = ? WHERE id = ?", (status, task_id)
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
def delete_task(task_id):
    with get_connection() as connection:
        cursor = connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        if cursor.rowcount == 0:
            return jsonify({"error": "Task not found."}), 404
    return ("", 204)
