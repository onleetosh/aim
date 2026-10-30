# Analytics: trends over weeks or months, planned vs actual time, downtime patterns,
# and stalled work. Everything is derived from data the user has logged.
from datetime import date, timedelta

from flask import Blueprint, jsonify, request

from .auth import login_required
from .database import get_connection
from .dates import parse_date


analytics_api = Blueprint("analytics_api", __name__)

# Constants for analytics calculations, such as stale task threshold, number of weeks/months to consider, and matrix categories.
STALE_DAYS = 7
WEEKS = 8
MONTHS = 6
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MATRIX_CATEGORIES = 5

# Helper function to calculate the start date of a given month.
def month_start(year, month):
    year += (month - 1) // 12
    month = (month - 1) % 12 + 1
    return date(year, month, 1)

# Helper function to build time buckets for analytics, either weekly or monthly.
def build_buckets(period, today):
    if period == "monthly":
        starts = [month_start(today.year, today.month - offset) for offset in range(MONTHS - 1, -1, -1)]
        ends = [month_start(s.year, s.month + 1) - timedelta(days=1) for s in starts]
        labels = [s.strftime("%b %Y") for s in starts]
    else:
        monday = today - timedelta(days=today.weekday())
        starts = [monday - timedelta(weeks=offset) for offset in range(WEEKS - 1, -1, -1)]
        ends = [s + timedelta(days=6) for s in starts]
        labels = [s.strftime("%b %d") for s in starts]
    return [
        {"label": label, "start": s.isoformat(), "end": e.isoformat()}
        for label, s, e in zip(labels, starts, ends)
    ]

# Helper function to determine which bucket a given day belongs to.
def bucket_of(buckets, day_text):
    for index, bucket in enumerate(buckets):
        if bucket["start"] <= day_text <= bucket["end"]:
            return index
    return None

# Helper function to calculate the change between current and previous values.
def change(current, previous):
    return {"current": current, "previous": previous, "delta": current - previous}


# Endpoint to fetch analytics data for the logged-in user.
@analytics_api.get("/api/analytics")
@login_required
# Returns analytics data based on the specified period (weekly or monthly) and the current date.
def get_analytics(user):
    period = "monthly" if request.args.get("period") == "monthly" else "weekly"
    today = date.fromisoformat(parse_date(request.args.get("today")) or date.today().isoformat())
    buckets = build_buckets(period, today)
    range_start = buckets[0]["start"]
    count = len(buckets)

    with get_connection() as connection:
        project_rows = connection.execute(
            "SELECT id, title FROM projects WHERE user_id = ? ORDER BY id", (user["id"],)
        ).fetchall()
        task_rows = connection.execute(
            "SELECT tasks.id, tasks.project_id, tasks.title, tasks.status, tasks.created_at, "
            "tasks.completed_on, tasks.updated_on, tasks.estimate_minutes, "
            "(SELECT COALESCE(SUM(minutes), 0) FROM work_sessions "
            " WHERE work_sessions.task_id = tasks.id) AS logged_minutes "
            "FROM tasks JOIN projects ON projects.id = tasks.project_id "
            "WHERE projects.user_id = ?",
            (user["id"],),
        ).fetchall()
        focus_rows = connection.execute(
            "SELECT entry_date, minutes FROM work_sessions WHERE user_id = ? AND entry_date >= ?",
            (user["id"], range_start),
        ).fetchall()
        downtime_rows = connection.execute(
            "SELECT entry_date, minutes, reason FROM downtime_entries "
            "WHERE user_id = ? AND entry_date >= ?",
            (user["id"], range_start),
        ).fetchall()

    tasks = [
        {
            "id": str(row["id"]),
            "project_id": row["project_id"],
            "title": row["title"],
            "status": row["status"],
            "created": str(row["created_at"])[:10],
            "completed": str(row["completed_on"]) if row["completed_on"] else None,
            "updated": str(row["updated_on"]) if row["updated_on"] else None,
            "estimate": row["estimate_minutes"],
            "logged": row["logged_minutes"],
        }
        for row in task_rows
    ]

    trend = []
    for bucket in buckets:
        start, end = bucket["start"], bucket["end"]
        completed = [t for t in tasks if t["status"] == "done" and t["completed"] and start <= t["completed"] <= end]
        # Tasks that existed and were still open (or finished in this period) at some point in it.
        in_play = [
            t for t in tasks
            if t["created"] <= end
            and (t["status"] != "done" or (t["completed"] and t["completed"] >= start))
        ]
        measured = [t for t in completed if t["estimate"] and t["logged"]]
        trend.append(
            {
                "label": bucket["label"],
                "start": start,
                "end": end,
                "created": sum(1 for t in tasks if start <= t["created"] <= end),
                "completed": len(completed),
                "inPlay": len(in_play),
                "completionRate": round(len(completed) / len(in_play) * 100) if in_play else None,
                "focusMinutes": 0,
                "downtimeMinutes": 0,
                "plannedMinutes": sum(t["estimate"] for t in measured),
                "actualMinutes": sum(t["logged"] for t in measured),
                "measuredTasks": len(measured),
            }
        )

    for row in focus_rows:
        index = bucket_of(buckets, str(row["entry_date"]))
        if index is not None:
            trend[index]["focusMinutes"] += row["minutes"]

    by_category = {}
    matrix = {}
    by_weekday = [0] * 7
    for row in downtime_rows:
        day_text = str(row["entry_date"])
        index = bucket_of(buckets, day_text)
        if index is None:
            continue
        trend[index]["downtimeMinutes"] += row["minutes"]
        category = row["reason"] or "Unspecified"
        weekday = date.fromisoformat(day_text).weekday()
        by_category[category] = by_category.get(category, 0) + row["minutes"]
        by_weekday[weekday] += row["minutes"]
        cells = matrix.setdefault(category, [0] * 7)
        cells[weekday] += row["minutes"]

    top_categories = sorted(by_category, key=lambda name: -by_category[name])[:MATRIX_CATEGORIES]
    downtime_total = sum(by_category.values())
    patterns = {
        "weekdays": WEEKDAYS,
        "byWeekday": by_weekday,
        "peakWeekday": WEEKDAYS[by_weekday.index(max(by_weekday))] if downtime_total else None,
        "totalMinutes": downtime_total,
        "categories": [
            {
                "category": name,
                "minutes": by_category[name],
                "share": round(by_category[name] / downtime_total * 100),
                "byWeekday": matrix[name],
            }
            for name in top_categories
        ],
    }

    # Stalled work: open tasks idle for a week or more, and projects whose latest activity is just as old.
    stalled_tasks = []
    last_activity = {}
    for t in tasks:
        latest = max(filter(None, (t["updated"], t["completed"], t["created"])))
        previous = last_activity.get(t["project_id"], "")
        last_activity[t["project_id"]] = max(previous, latest)
        if t["status"] != "done" and (today - date.fromisoformat(latest)).days >= STALE_DAYS:
            stalled_tasks.append(
                {"id": t["id"], "title": t["title"], "status": t["status"],
                 "project_id": t["project_id"], "daysIdle": (today - date.fromisoformat(latest)).days}
            )
    titles = {row["id"]: row["title"] for row in project_rows}
    stalled_projects = []
    for row in project_rows:
        project_tasks = [t for t in tasks if t["project_id"] == row["id"]]
        open_count = sum(1 for t in project_tasks if t["status"] != "done")
        if not open_count:
            continue
        idle = (today - date.fromisoformat(last_activity[row["id"]])).days
        if idle >= STALE_DAYS:
            stalled_projects.append({"id": str(row["id"]), "title": row["title"], "openTasks": open_count, "daysIdle": idle})
    stalled_projects.sort(key=lambda item: -item["daysIdle"])
    stalled_tasks.sort(key=lambda item: -item["daysIdle"])
    for item in stalled_tasks:
        item["project"] = titles.get(item.pop("project_id"), "")

    current, previous = trend[-1], trend[-2]
    return jsonify(
        {
            "period": period,
            "staleDays": STALE_DAYS,
            "trend": trend,
            "comparison": {
                "completed": change(current["completed"], previous["completed"]),
                "focusMinutes": change(current["focusMinutes"], previous["focusMinutes"]),
                "downtimeMinutes": change(current["downtimeMinutes"], previous["downtimeMinutes"]),
            },
            "planVsActual": {
                "plannedMinutes": sum(b["plannedMinutes"] for b in trend),
                "actualMinutes": sum(b["actualMinutes"] for b in trend),
                "measuredTasks": sum(b["measuredTasks"] for b in trend),
            },
            "downtimePatterns": patterns,
            "stalled": {
                "projects": stalled_projects,
                "tasks": stalled_tasks[:15],
                "taskCount": len(stalled_tasks),
            },
            "bucketCount": count,
        }
    )
