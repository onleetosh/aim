# Dashboard: connects projects (intention), tasks (action), completion history
# (momentum), and downtime (awareness) into one summary with plain-language insights.
from datetime import date, timedelta

from flask import Blueprint, jsonify, request

from .auth import login_required
from .database import get_connection
from .dates import parse_date
from .focus import read_available_minutes


dashboard_api = Blueprint("dashboard_api", __name__)

WINDOW_DAYS = 7
HISTORY_DAYS = 14
STALE_DAYS = 7
OPEN_STATUSES = ("new", "ready", "progress", "review")
WIP_LIMIT = 3
UNRECORDED_WARN_PERCENT = 50
ESTIMATE_HIGH_PERCENT = 125
ESTIMATE_LOW_PERCENT = 75
HEAVY_DAY_SHARE = 0.8
HEAVY_DAYS_FOR_REST = 4


def recommend(tasks, counts, momentum, focus, downtime, stale, accounting, heavy_days):
    """Pick one next move from how intention, effort, and progress relate.

    More logged hours is never treated as the goal: the options are to focus,
    reduce the load, rest, or keep going. Rules are checked in priority order.
    """
    finished = momentum["completedThisWeek"]
    if not counts["total"]:
        return {
            "kind": "start",
            "headline": "Define one small first step",
            "reasons": ["You have no tasks yet, so there is nothing to measure."],
        }

    if heavy_days >= HEAVY_DAYS_FOR_REST and finished == 0:
        return {
            "kind": "rest",
            "headline": "Take a real break before adding more",
            "reasons": [
                f"You logged heavy focus on {heavy_days} of the last {WINDOW_DAYS} days but finished no tasks.",
                "More hours aren't converting into progress. Rest, then pick one smaller task.",
            ],
        }

    open_tasks = [task for task in tasks if task["status"] != "done"]
    if counts["progress"] > WIP_LIMIT:
        candidates = [t for t in open_tasks if t["status"] == "review"] or sorted(
            (t for t in open_tasks if t["status"] == "progress"), key=lambda t: -t["logged"]
        )
        reasons = [f"{counts['progress']} tasks are in progress at once, which splits your attention."]
        if candidates:
            reasons.append(f"Finish \"{candidates[0]['title']}\" first and pause the rest.")
        return {"kind": "focus", "headline": "Focus on one task", "reasons": reasons}

    if stale["count"] >= 3 or (stale["count"] and stale["count"] >= counts["open"] / 2):
        return {
            "kind": "reduce",
            "headline": "Reduce your workload",
            "reasons": [
                f"{stale['count']} of {counts['open']} open tasks haven't moved in {STALE_DAYS}+ days.",
                "Delete, defer, or shrink them so your board shows what you will really do.",
            ],
        }

    if downtime["totalMinutes"] and downtime["totalMinutes"] >= focus["weekMinutes"] and finished == 0:
        top = downtime["reasons"][0]["reason"]
        return {
            "kind": "reduce",
            "headline": "Look at what is pulling you away",
            "reasons": [
                f"Downtime ({downtime['totalMinutes']} min) outweighed focus ({focus['weekMinutes']} min) and nothing finished.",
                f"Your biggest reason was \"{top}\". Address that before adding work.",
            ],
        }

    if finished and heavy_days < HEAVY_DAYS_FOR_REST:
        return {
            "kind": "continue",
            "headline": "Keep going at this pace",
            "reasons": [
                f"{finished} task(s) finished this week without a pattern of overwork.",
                "Don't add hours; protect what is working.",
            ],
        }

    if heavy_days >= HEAVY_DAYS_FOR_REST:
        return {
            "kind": "rest",
            "headline": "Watch for overload",
            "reasons": [
                f"Focus filled most of your available time on {heavy_days} of {WINDOW_DAYS} days.",
                "Progress is happening, but plan a lighter day to sustain it.",
            ],
        }

    ready = [t for t in open_tasks if t["status"] in ("ready", "progress", "review")]
    return {
        "kind": "focus",
        "headline": "Pick the next task and start it",
        "reasons": [
            "Nothing finished this week and nothing is overloaded.",
            f"\"{ready[0]['title']}\" is already lined up." if ready else "Move one task to Ready.",
        ],
    }


def project_state(project, week_start):
    tasks = project["tasks"]
    total = len(tasks)
    done = [task for task in tasks if task["status"] == "done"]
    in_flight = [task for task in tasks if task["status"] in ("progress", "review")]
    recent = [task for task in done if (task["completed_on"] or "") >= week_start]
    if not total:
        label = "Needs a first step"
    elif len(done) == total:
        label = "Complete"
    elif recent:
        label = "Moving"
    elif in_flight:
        label = "In progress"
    else:
        label = "Stalled"
    return {
        "id": str(project["id"]),
        "title": project["title"],
        "total": total,
        "done": len(done),
        "percent": round(len(done) / total * 100) if total else 0,
        "label": label,
    }


def build_insights(projects, counts, momentum, downtime, stale, focus, plan, accounting):
    insights = []
    if stale["count"]:
        oldest = stale["tasks"][0]
        insights.append(
            {
                "kind": "hinder",
                "text": f"{stale['count']} open task(s) haven't changed in {STALE_DAYS}+ days. Oldest: \"{oldest['title']}\" ({oldest['daysIdle']} days). Move it, break it down, or delete it.",
            }
        )
    if focus["weekMinutes"] and momentum["completedThisWeek"]:
        per_task = round(focus["weekMinutes"] / momentum["completedThisWeek"])
        insights.append(
            {
                "kind": "help",
                "text": f"About {per_task} min of focus per finished task this week. Compare this over time rather than chasing a bigger total.",
            }
        )
    elif focus["weekMinutes"]:
        insights.append(
            {
                "kind": "hinder",
                "text": f"{focus['weekMinutes']} min of focus this week but no task finished. Effort isn't turning into completed work.",
            }
        )
    if plan["taskCount"]:
        if plan["percent"] >= ESTIMATE_HIGH_PERCENT:
            insights.append(
                {
                    "kind": "hinder",
                    "text": f"Finished tasks took {plan['percent']}% of their estimates. Plan fewer tasks or add buffer to estimates.",
                }
            )
        elif plan["percent"] <= ESTIMATE_LOW_PERCENT:
            insights.append(
                {
                    "kind": "help",
                    "text": f"Finished tasks took {plan['percent']}% of their estimates. Your estimates run long, so trim them rather than adding work.",
                }
            )
        else:
            insights.append(
                {"kind": "help", "text": f"Estimates are realistic: tasks took {plan['percent']}% of the planned time."}
            )
    if accounting["unrecordedPercent"] >= UNRECORDED_WARN_PERCENT:
        insights.append(
            {
                "kind": "next",
                "text": f"{accounting['unrecordedPercent']}% of your available time this week isn't logged, so these totals are partial. Unlogged time is not necessarily lost time.",
            }
        )
    if momentum["activeDays"] == 0 and counts["open"]:
        insights.append(
            {"kind": "hinder", "text": f"No tasks finished in the last {WINDOW_DAYS} days."}
        )
    elif momentum["activeDays"] >= 4:
        insights.append(
            {
                "kind": "help",
                "text": f"You finished work on {momentum['activeDays']} of the last {WINDOW_DAYS} days. Consistency is working.",
            }
        )
    if momentum["streak"] >= 2:
        insights.append({"kind": "help", "text": f"{momentum['streak']}-day completion streak."})

    if counts["progress"] > WIP_LIMIT:
        insights.append(
            {
                "kind": "hinder",
                "text": f"{counts['progress']} tasks are in progress at once, which spreads your attention. Finish one before starting another.",
            }
        )
    if counts["review"]:
        insights.append(
            {
                "kind": "next",
                "text": f"{counts['review']} task(s) are waiting in review. Closing them is the quickest win.",
            }
        )

    if downtime["totalMinutes"]:
        top = downtime["reasons"][0]
        share = round(top["minutes"] / downtime["totalMinutes"] * 100)
        insights.append(
            {
                "kind": "hinder",
                "text": f"\"{top['reason']}\" took {top['minutes']} min ({share}% of your downtime) this week.",
            }
        )
        active_avg, idle_avg = downtime["avgOnActiveDays"], downtime["avgOnInactiveDays"]
        if active_avg is not None and idle_avg is not None and idle_avg > active_avg:
            insights.append(
                {
                    "kind": "hinder",
                    "text": f"Days with no finished tasks averaged {idle_avg} min of downtime versus {active_avg} min on days you finished work.",
                }
            )

    for project in [p for p in projects if p["label"] == "Stalled"][:2]:
        insights.append(
            {
                "kind": "next",
                "text": f"\"{project['title']}\" has open tasks but no movement. Move one task to Ready.",
            }
        )
    for project in [p for p in projects if p["label"] == "Needs a first step"][:1]:
        insights.append(
            {"kind": "next", "text": f"\"{project['title']}\" has no tasks yet. Add its first step."}
        )
    if not projects:
        insights.append({"kind": "next", "text": "Create a project to state what you are working toward."})
    return insights


@dashboard_api.get("/api/dashboard")
@login_required
def get_dashboard(user):
    today_text = parse_date(request.args.get("today")) or date.today().isoformat()
    today = date.fromisoformat(today_text)
    week_start = (today - timedelta(days=WINDOW_DAYS - 1)).isoformat()
    history_start = (today - timedelta(days=HISTORY_DAYS - 1)).isoformat()

    with get_connection() as connection:
        project_rows = connection.execute(
            "SELECT id, title FROM projects WHERE user_id = ? ORDER BY id", (user["id"],)
        ).fetchall()
        projects = {row["id"]: {"id": row["id"], "title": row["title"], "tasks": []} for row in project_rows}
        task_rows = connection.execute(
            "SELECT tasks.id, tasks.project_id, tasks.title, tasks.status, tasks.completed_on, "
            "tasks.updated_on, tasks.estimate_minutes, "
            "(SELECT COALESCE(SUM(minutes), 0) FROM work_sessions "
            " WHERE work_sessions.task_id = tasks.id) AS logged_minutes "
            "FROM tasks JOIN projects ON projects.id = tasks.project_id "
            "WHERE projects.user_id = ?",
            (user["id"],),
        ).fetchall()
        for row in task_rows:
            projects[row["project_id"]]["tasks"].append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "status": row["status"],
                    "completed_on": row["completed_on"],
                    "updated_on": row["updated_on"],
                    "estimate": row["estimate_minutes"],
                    "logged": row["logged_minutes"],
                }
            )
        downtime_rows = connection.execute(
            "SELECT entry_date, minutes, reason FROM downtime_entries "
            "WHERE user_id = ? AND entry_date >= ?",
            (user["id"], week_start),
        ).fetchall()
        focus_rows = connection.execute(
            "SELECT entry_date, minutes FROM work_sessions "
            "WHERE user_id = ? AND entry_date >= ?",
            (user["id"], week_start),
        ).fetchall()
        available = read_available_minutes(connection, user["id"])

    tasks = [task for project in projects.values() for task in project["tasks"]]
    counts = {
        status: sum(1 for task in tasks if task["status"] == status)
        for status in (*OPEN_STATUSES, "done")
    }
    counts["total"] = len(tasks)
    counts["open"] = sum(counts[status] for status in OPEN_STATUSES)

    completed_by_day = {}
    for task in tasks:
        if task["status"] == "done" and task["completed_on"] and task["completed_on"] >= history_start:
            completed_by_day[task["completed_on"]] = completed_by_day.get(task["completed_on"], 0) + 1
    history = []
    for offset in range(HISTORY_DAYS - 1, -1, -1):
        day = (today - timedelta(days=offset)).isoformat()
        history.append({"date": day, "completed": completed_by_day.get(day, 0)})
    week = [day for day in history if day["date"] >= week_start]
    active_dates = {day["date"] for day in week if day["completed"]}

    # A streak stays alive through today even if nothing is finished yet today.
    streak = 0
    cursor = today if today_text in completed_by_day else today - timedelta(days=1)
    while cursor.isoformat() in completed_by_day:
        streak += 1
        cursor -= timedelta(days=1)

    # Momentum score: share of the last 7 days with at least one finished task.
    momentum = {
        "percent": round(len(active_dates) / WINDOW_DAYS * 100),
        "activeDays": len(active_dates),
        "windowDays": WINDOW_DAYS,
        "streak": streak,
        "completedThisWeek": sum(day["completed"] for day in week),
        "history": history,
    }

    downtime_by_day = {}
    reasons = {}
    for row in downtime_rows:
        day = str(row["entry_date"])
        downtime_by_day[day] = downtime_by_day.get(day, 0) + row["minutes"]
        key = row["reason"] or "Unspecified"
        reasons[key] = reasons.get(key, 0) + row["minutes"]

    def average(days):
        if not days:
            return None
        return round(sum(downtime_by_day.get(day, 0) for day in days) / len(days))

    week_dates = [day["date"] for day in week]
    downtime = {
        "totalMinutes": sum(reasons.values()),
        "reasons": [
            {
                "reason": reason,
                "minutes": minutes,
                "share": round(minutes / sum(reasons.values()) * 100),
            }
            for reason, minutes in sorted(reasons.items(), key=lambda item: -item[1])
        ][:8],
        "avgOnActiveDays": average([day for day in week_dates if day in active_dates]),
        "avgOnInactiveDays": average([day for day in week_dates if day not in active_dates]),
    }

    summaries = [project_state(project, week_start) for project in projects.values()]
    open_projects = [project for project in summaries if project["label"] != "Complete"]

    project_titles = {project["id"]: project["title"] for project in projects.values()}
    stale_tasks = []
    for project in projects.values():
        for task in project["tasks"]:
            if task["status"] == "done" or not task["updated_on"]:
                continue
            idle = (today - date.fromisoformat(str(task["updated_on"]))).days
            if idle >= STALE_DAYS:
                stale_tasks.append(
                    {"id": str(task["id"]), "title": task["title"], "project": project_titles[project["id"]], "daysIdle": idle}
                )
    stale_tasks.sort(key=lambda task: -task["daysIdle"])
    stale = {"days": STALE_DAYS, "count": len(stale_tasks), "tasks": stale_tasks[:5]}

    focus_by_day = {}
    for row in focus_rows:
        day = str(row["entry_date"])
        focus_by_day[day] = focus_by_day.get(day, 0) + row["minutes"]
    focus = {
        "weekMinutes": sum(focus_by_day.values()),
        "daysWithFocus": len(focus_by_day),
    }

    # Plan accuracy only uses finished tasks that have both an estimate and logged sessions.
    measured = [
        task for task in tasks
        if task["status"] == "done" and task["estimate"] and task["logged"]
    ]
    estimated_total = sum(task["estimate"] for task in measured)
    actual_total = sum(task["logged"] for task in measured)
    plan = {
        "taskCount": len(measured),
        "estimatedMinutes": estimated_total,
        "actualMinutes": actual_total,
        "percent": round(actual_total / estimated_total * 100) if estimated_total else 0,
        "finishedWithoutData": sum(
            1 for task in tasks
            if task["status"] == "done" and not (task["estimate"] and task["logged"])
        ),
        "tasks": [
            {"title": task["title"], "estimate": task["estimate"], "logged": task["logged"]}
            for task in sorted(measured, key=lambda t: -abs(t["logged"] - t["estimate"]))[:5]
        ],
    }

    # Unrecorded time is available time minus everything logged, per day, never below zero.
    available_total = available * WINDOW_DAYS
    unrecorded = sum(
        max(0, available - downtime_by_day.get(day, 0) - focus_by_day.get(day, 0))
        for day in week_dates
    )
    accounting = {
        "availablePerDay": available,
        "availableMinutes": available_total,
        "focusMinutes": focus["weekMinutes"],
        "downtimeMinutes": downtime["totalMinutes"],
        "unrecordedMinutes": unrecorded,
        "unrecordedPercent": round(unrecorded / available_total * 100) if available_total else 0,
        "daysWithAnyLog": len(set(focus_by_day) | set(downtime_by_day)),
    }

    # Heavy days: focus filled most of the available time (a signal of overload, not success).
    heavy_days = sum(
        1 for day in week_dates if focus_by_day.get(day, 0) >= HEAVY_DAY_SHARE * available
    )
    recommendation = recommend(
        tasks, counts, momentum, focus, downtime, stale, accounting, heavy_days
    )

    # Priorities are derived, not user-set: work already underway first, oldest-idle first.
    rank = {"review": 0, "progress": 1, "ready": 2}
    why = {"review": "In review: close it out", "progress": "Already in progress", "ready": "Ready to start"}
    candidates = [
        (rank[task["status"]], str(task["updated_on"] or ""), task, project["title"])
        for project in projects.values()
        for task in project["tasks"]
        if task["status"] in rank
    ]
    candidates.sort(key=lambda item: (item[0], item[1]))
    priorities = [
        {
            "id": str(task["id"]),
            "title": task["title"],
            "project": project_title,
            "status": task["status"],
            "why": why[task["status"]],
        }
        for _, _, task, project_title in candidates[:WIP_LIMIT]
    ]

    active_tasks = [task for project in projects.values() if any(
        p["id"] == str(project["id"]) and p["label"] != "Complete" for p in summaries
    ) for task in project["tasks"]]
    active_done = sum(1 for task in active_tasks if task["status"] == "done")
    overview = {
        "activeProjects": len(open_projects),
        "totalProjects": len(summaries),
        "activeDone": active_done,
        "activeTotal": len(active_tasks),
        "activePercent": round(active_done / len(active_tasks) * 100) if active_tasks else 0,
    }

    return jsonify(
        {
            "priorities": priorities,
            "overview": overview,
            "recommendation": recommendation,
            "intention": {
                "projects": summaries,
                "moving": sum(1 for p in open_projects if p["label"] in ("Moving", "In progress")),
                "open": len(open_projects),
            },
            "action": {
                "counts": counts,
                "completionRate": round(counts["done"] / counts["total"] * 100) if counts["total"] else 0,
                "stale": stale,
            },
            "momentum": momentum,
            "focus": focus,
            "planAccuracy": plan,
            "accounting": accounting,
            "awareness": {
                "downtime": downtime,
                "insights": build_insights(
                    summaries, counts, momentum, downtime, stale, focus, plan, accounting
                ),
            },
        }
    )
