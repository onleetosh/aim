import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "aim.db"


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
                status TEXT NOT NULL DEFAULT 'new'
                    CHECK(status IN ('new', 'ready', 'progress', 'review', 'done')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
            """
        )
        task_columns = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'tasks'"
        ).fetchone()[0]
        if "CHECK(status IN ('ready', 'progress', 'review', 'done'))" in task_columns:
            connection.executescript(
                """
                ALTER TABLE tasks RENAME TO tasks_old;
                CREATE TABLE tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    title TEXT NOT NULL CHECK(length(trim(title)) > 0),
                    description TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'new'
                        CHECK(status IN ('new', 'ready', 'progress', 'review', 'done')),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
                );
                INSERT INTO tasks (id, project_id, title, description, status, created_at)
                    SELECT id, project_id, title, description, status, created_at
                    FROM tasks_old;
                DROP TABLE tasks_old;
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
