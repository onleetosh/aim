# PostgreSQL connection management and schema creation.
import os

import psycopg
from psycopg.rows import dict_row


def database_url():
    return os.environ.get("DATABASE_URL", "").strip()


class Connection:
    """Keep the application's question-mark placeholders on PostgreSQL."""

    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql, params=()):
        return self.raw.execute(sql.replace("?", "%s"), params)

    def executemany(self, sql, rows):
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
    if not url:
        raise RuntimeError(
            "DATABASE_URL must be set to a PostgreSQL connection string."
        )
    return Connection(psycopg.connect(url, row_factory=dict_row))


def initialize_database():
    with get_connection() as connection:
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
        # Completion dates feed the dashboard's momentum measures.
        connection.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS completed_on TEXT")


def add_task_column(connection, name, definition):
    connection.execute(f"ALTER TABLE tasks ADD COLUMN IF NOT EXISTS {name} {definition}")


def initialize_tracking_tables():
    with get_connection() as connection:
        # updated_on drives stale-work detection; estimate_minutes drives plan accuracy.
        add_task_column(connection, "updated_on", "TEXT")
        add_task_column(connection, "estimate_minutes", "INTEGER")
        # Archived tasks stay done but are hidden from the kanban board.
        add_task_column(connection, "archived", "INTEGER NOT NULL DEFAULT 0")
        connection.execute(
            "UPDATE tasks SET updated_on = substr(CAST(created_at AS TEXT), 1, 10) "
            "WHERE updated_on IS NULL"
        )
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS work_sessions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
                entry_date TEXT NOT NULL,
                minutes INTEGER NOT NULL CHECK(minutes > 0),
                note TEXT NOT NULL DEFAULT ''
            )
            """
        )
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS user_settings (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
                available_minutes_per_day INTEGER NOT NULL DEFAULT 480
            )
            """
        )
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS downtime_entries (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                entry_date TEXT NOT NULL,
                minutes INTEGER NOT NULL CHECK(minutes > 0),
                reason TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT ''
            )
            """
        )


def integrity_errors():
    return (psycopg.IntegrityError,)
