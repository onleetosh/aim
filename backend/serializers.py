# Convert database rows to the camelCase shape expected by the browser.
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
            """
            SELECT tasks.id, tasks.project_id, tasks.title, tasks.description, tasks.status
            FROM tasks
            JOIN projects ON projects.id = tasks.project_id
            WHERE projects.user_id = ?
            ORDER BY tasks.id
            """,
            (user_id,),
        )
    ]
    return {"projects": projects, "tasks": tasks}
