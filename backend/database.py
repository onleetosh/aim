# Database connection management, schema creation, and demo seed data.
# PostgreSQL is used when DATABASE_URL is set (deployment); otherwise a local
# SQLite file is used so development needs no extra setup.
import os
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "aim.db"


def database_url():
    return os.environ.get("DATABASE_URL", "").strip()


class Connection:
    """Small wrapper giving SQLite and PostgreSQL the same execute() interface."""

    def __init__(self, raw, postgres):
        self.raw = raw
        self.postgres = postgres

    def execute(self, sql, params=()):
        if not self.postgres:
            return self.raw.execute(sql, params)
        sql = sql.replace("?", "%s")
        is_insert = sql.lstrip().upper().startswith("INSERT")
        if is_insert:
            sql += " RETURNING id"
        cursor = self.raw.execute(sql, params)
        if is_insert:
            cursor.lastrowid = cursor.fetchone()["id"]
        return cursor

    def executemany(self, sql, rows):
        if not self.postgres:
            return self.raw.executemany(sql, rows)
        cursor = self.raw.cursor()
        cursor.executemany(sql.replace("?", "%s"), rows)
        return cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        try:
            if exc_type is None:
                self.raw.commit()
            else:
                self.raw.rollback()
        finally:
            self.raw.close()


def get_connection():
    url = database_url()
    if url:
        import psycopg
        from psycopg.rows import dict_row

        return Connection(psycopg.connect(url, row_factory=dict_row), True)
    # Row objects let serializers address columns by name instead of position.
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return Connection(connection, False)


def initialize_database():
    with get_connection() as connection:
        if connection.postgres:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL CHECK(length(trim(title)) > 0),
                    description TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            # Databases created before accounts existed get an owner column.
            connection.execute(
                """
                ALTER TABLE projects ADD COLUMN IF NOT EXISTS user_id INTEGER
                    REFERENCES users(id) ON DELETE CASCADE
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id SERIAL PRIMARY KEY,
                    project_id INTEGER NOT NULL
                        REFERENCES projects(id) ON DELETE CASCADE,
                    title TEXT NOT NULL CHECK(length(trim(title)) > 0),
                    description TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'new'
                        CHECK(status IN ('new', 'ready', 'progress', 'review', 'done')),
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            return
        connection.raw.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

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
        # Rebuild databases created before the "new" task status was introduced.
        if "CHECK(status IN ('ready', 'progress', 'review', 'done'))" in task_columns:
            connection.raw.executescript(
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
        # Databases created before accounts existed get an owner column.
        project_columns = [
            row["name"] for row in connection.execute("PRAGMA table_info(projects)")
        ]
        if "user_id" not in project_columns:
            connection.execute(
                "ALTER TABLE projects ADD COLUMN user_id INTEGER "
                "REFERENCES users(id) ON DELETE CASCADE"
            )


def integrity_errors():
    errors = [sqlite3.IntegrityError]
    if database_url():
        import psycopg

        errors.append(psycopg.IntegrityError)
    return tuple(errors)
