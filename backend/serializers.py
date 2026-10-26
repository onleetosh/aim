# Convert database rows to the camelCase shape expected by the browser.
TASK_SELECT = """
    SELECT tasks.id, tasks.project_id, tasks.title, tasks.description, tasks.status,
           tasks.updated_on, tasks.estimate_minutes, tasks.completed_on, tasks.archived,
           (SELECT COALESCE(SUM(minutes), 0) FROM work_sessions
            WHERE work_sessions.task_id = tasks.id) AS logged_minutes
    FROM tasks
"""


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
        "updatedOn": row["updated_on"],
        "completedOn": str(row["completed_on"]) if row["completed_on"] else None,
        "archived": bool(row["archived"]),
        "estimateMinutes": row["estimate_minutes"],
        "loggedMinutes": row["logged_minutes"],
    }


def state_response(connection, user_id):
    projects = [
        project_from_row(row)
        for row in connection.execute(
            "SELECT id, title, description FROM projects WHERE user_id = ? ORDER BY id",
            (user_id,),
        )
    ]
    tasks = [
        task_from_row(row)
        for row in connection.execute(
            TASK_SELECT
            + """
            JOIN projects ON projects.id = tasks.project_id
            WHERE projects.user_id = ?
            ORDER BY tasks.id
            """,
            (user_id,),
        )
    ]
    return {"projects": projects, "tasks": tasks}
