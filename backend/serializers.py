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
