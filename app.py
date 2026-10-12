from pathlib import Path
import sqlite3

from flask import Flask, jsonify, request, send_from_directory


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "aim.db"
app = Flask(__name__, static_folder=str(BASE_DIR), static_url_path="")


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database():
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL CHECK(length(trim(title)) > 0),
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                title TEXT NOT NULL CHECK(length(trim(title)) > 0),
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'ready'
                    CHECK(status IN ('ready', 'progress', 'review', 'done')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
            """
        )
        if connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0:
            projects = [
                ("Finish coursework", "Keep the semester moving forward."),
                ("Build A.I.M.", "Turn the idea into a useful first version."),
            ]
            connection.executemany(
                "INSERT INTO projects (title, description) VALUES (?, ?)", projects
            )
            project_ids = {
                row["title"]: row["id"]
                for row in connection.execute("SELECT id, title FROM projects")
            }
            connection.executemany(
                """
                INSERT INTO tasks (project_id, title, description, status)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (project_ids["Finish coursework"], "Outline the research paper",
                     "Draft the sections and add the first sources.", "progress"),
                    (project_ids["Build A.I.M."], "Sketch the board layout",
                     "Decide what information needs to be visible at a glance.", "review"),
                    (project_ids["Finish coursework"], "Complete assigned reading", "", "ready"),
                    (project_ids["Build A.I.M."], "Write the project intro", "", "done"),
                ],
            )


def project_from_row(row):
    return {
        "id": str(row["id"]),
        "title": row["title"],
        "description": row["description"],
    }


def task_from_row(row):
    return {
        "id": str(row["id"]),
        "projectId": str(row["project_id"]),
        "title": row["title"],
        "description": row["description"],
        "status": row["status"],
    }


def state_response(connection):
    projects = [
        project_from_row(row)
        for row in connection.execute(
            "SELECT id, title, description FROM projects ORDER BY id"
        )
    ]
    tasks = [
        task_from_row(row)
        for row in connection.execute(
            """
            SELECT id, project_id, title, description, status
            FROM tasks
            ORDER BY id
            """
        )
    ]
    return {"projects": projects, "tasks": tasks}


@app.get("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/api/state")
def get_state():
    with get_connection() as connection:
        return jsonify(state_response(connection))


@app.post("/api/projects")
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


@app.post("/api/tasks")
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


@app.patch("/api/tasks/<int:task_id>")
def update_task(task_id):
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    allowed_statuses = {"ready", "progress", "review", "done"}
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


@app.delete("/api/tasks/<int:task_id>")
def delete_task(task_id):
    with get_connection() as connection:
        cursor = connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        if cursor.rowcount == 0:
            return jsonify({"error": "Task not found."}), 404
    return ("", 204)


initialize_database()


if __name__ == "__main__":
    app.run(debug=True)
