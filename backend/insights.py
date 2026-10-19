# Insights: recurring patterns, a realistic daily plan, tasks worth resuming, period
# comparison, and data-backed recommendations. Every insight carries its evidence, and
# patterns are only reported when enough data supports them. More hours is never the goal.
from collections import Counter, defaultdict
from datetime import date, timedelta
from statistics import median

from flask import Blueprint, jsonify, request

from .auth import login_required
from .database import get_connection
from .dates import parse_date
from .focus import read_available_minutes


insights_api = Blueprint("insights_api", __name__)

HISTORY_DAYS = 28
STALE_DAYS = 7
WIP_LIMIT = 3
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MIN_LOGGED_DAYS = 5
MIN_COMPLETIONS = 3
MIN_MEASURED_TASKS = 3
MIN_FOCUS_DAYS = 3
SHARE_THRESHOLD = 0.4
CATEGORY_MIN_DAYS = 3
CATEGORY_MIN_SHARE = 0.25
ESTIMATE_HIGH = 1.25
ESTIMATE_LOW = 0.75
HEAVY_DAY_SHARE = 0.8
FALLBACK_CAPACITY_SHARE = 0.6
UNESTIMATED_MINUTES = 45
MIN_TASK_MINUTES = 15
BIAS_RANGE = (0.5, 2.0)
MAX_COMPARE_DAYS = 366


def weekday_of(day_text):
    return date.fromisoformat(day_text).weekday()


def load_data(user_id, since):
    with get_connection() as connection:
        task_rows = connection.execute(
            "SELECT tasks.id, tasks.title, tasks.status, tasks.created_at, tasks.completed_on, "
            "tasks.updated_on, tasks.estimate_minutes, projects.title AS project_title, "
            "(SELECT COALESCE(SUM(minutes), 0) FROM work_sessions "
            " WHERE work_sessions.task_id = tasks.id) AS logged_minutes "
            "FROM tasks JOIN projects ON projects.id = tasks.project_id "
            "WHERE projects.user_id = ?",
            (user_id,),
        ).fetchall()
        focus_rows = connection.execute(
            "SELECT entry_date, minutes FROM work_sessions WHERE user_id = ? AND entry_date >= ?",
            (user_id, since),
        ).fetchall()
        downtime_rows = connection.execute(
            "SELECT entry_date, minutes, reason FROM downtime_entries "
            "WHERE user_id = ? AND entry_date >= ?",
            (user_id, since),
        ).fetchall()
        available = read_available_minutes(connection, user_id)

    tasks = []
    for row in task_rows:
        created = str(row["created_at"])[:10]
        completed = str(row["completed_on"]) if row["completed_on"] else None
        updated = str(row["updated_on"]) if row["updated_on"] else None
        tasks.append(
            {
                "id": str(row["id"]),
                "title": row["title"],
                "project": row["project_title"],
                "status": row["status"],
                "created": created,
                "completed": completed,
                "lastActivity": max(filter(None, (created, completed, updated))),
                "estimate": row["estimate_minutes"],
                "logged": row["logged_minutes"],
            }
        )
    focus = [(str(r["entry_date"]), r["minutes"]) for r in focus_rows]
    downtime = [(str(r["entry_date"]), r["minutes"], r["reason"]) for r in downtime_rows]
    return tasks, focus, downtime, available


def estimate_bias(tasks, since):
    measured = [
        t for t in tasks
        if t["status"] == "done" and t["completed"] and t["completed"] >= since
        and t["estimate"] and t["logged"]
    ]
    planned = sum(t["estimate"] for t in measured)
    actual = sum(t["logged"] for t in measured)
    return len(measured), (actual / planned if planned else None)


def find_patterns(tasks, focus, downtime, available, since):
    patterns = []
    completions = [t["completed"] for t in tasks if t["status"] == "done" and t["completed"] and t["completed"] >= since]

    by_weekday = Counter(weekday_of(day) for day in completions)
    if len(completions) >= MIN_COMPLETIONS and by_weekday:
        day, count = by_weekday.most_common(1)[0]
        if count >= 2 and count / len(completions) >= SHARE_THRESHOLD:
            patterns.append({
                "id": "finish-day",
                "title": f"You tend to finish work on {WEEKDAYS[day]}s",
                "detail": f"{count} of your last {len(completions)} finished tasks were completed on a {WEEKDAYS[day]}. Protect that day for closing out tasks.",
            })

    downtime_total = sum(minutes for _, minutes, _ in downtime)
    if len(downtime) >= 4 and downtime_total:
        minutes_by_day = defaultdict(int)
        for day_text, minutes, _ in downtime:
            minutes_by_day[weekday_of(day_text)] += minutes
        day, minutes = max(minutes_by_day.items(), key=lambda item: item[1])
        if minutes / downtime_total >= 0.3:
            patterns.append({
                "id": "downtime-day",
                "title": f"Downtime clusters on {WEEKDAYS[day]}s",
                "detail": f"{round(minutes / downtime_total * 100)}% of logged downtime ({minutes} min) falls on {WEEKDAYS[day]}. Plan lighter work or a deliberate break that day.",
            })

        days_by_reason = defaultdict(set)
        minutes_by_reason = defaultdict(int)
        for day_text, mins, reason in downtime:
            days_by_reason[reason].add(day_text)
            minutes_by_reason[reason] += mins
        reason, mins = max(minutes_by_reason.items(), key=lambda item: item[1])
        if len(days_by_reason[reason]) >= CATEGORY_MIN_DAYS and mins / downtime_total >= CATEGORY_MIN_SHARE:
            patterns.append({
                "id": "downtime-reason",
                "title": f"\"{reason}\" keeps recurring as downtime",
                "detail": f"It appeared on {len(days_by_reason[reason])} different days and makes up {round(mins / downtime_total * 100)}% of downtime. Address it directly instead of absorbing it.",
            })

    count, bias = estimate_bias(tasks, since)
    if count >= MIN_MEASURED_TASKS and bias is not None:
        if bias >= ESTIMATE_HIGH:
            patterns.append({
                "id": "underestimate",
                "title": "Tasks usually take longer than planned",
                "detail": f"Across {count} finished tasks, actual time was {round(bias * 100)}% of the estimate. Pad estimates or plan fewer tasks.",
            })
        elif bias <= ESTIMATE_LOW:
            patterns.append({
                "id": "overestimate",
                "title": "You tend to overestimate tasks",
                "detail": f"Across {count} finished tasks, actual time was {round(bias * 100)}% of the estimate. You may be able to plan a little more.",
            })

    focus_by_day = defaultdict(int)
    for day_text, minutes in focus:
        focus_by_day[day_text] += minutes
    finished_days = set(completions)
    heavy_unfinished = [d for d, m in focus_by_day.items() if m >= available * HEAVY_DAY_SHARE and d not in finished_days]
    if len(heavy_unfinished) >= 3:
        patterns.append({
            "id": "long-days-no-finish",
            "title": "Long work days that finish nothing",
            "detail": f"{len(heavy_unfinished)} days with heavy focus time ended without a completed task. Narrow to one task and define what done looks like.",
        })
    return patterns


def build_plan(tasks, focus, available, bias_value, bias_count, since):
    focus_by_day = defaultdict(int)
    for day_text, minutes in focus:
        focus_by_day[day_text] += minutes
    if len(focus_by_day) >= MIN_FOCUS_DAYS:
        typical = int(median(focus_by_day.values()))
        capacity = min(available, typical)
        capacity_basis = f"Your typical focused day over the last {HISTORY_DAYS} days is {typical} min."
    else:
        capacity = int(available * FALLBACK_CAPACITY_SHARE)
        capacity_basis = f"Not enough logged focus days yet, so this assumes {round(FALLBACK_CAPACITY_SHARE * 100)}% of your available time."

    factor = 1.0
    bias_note = None
    if bias_count >= MIN_MEASURED_TASKS and bias_value:
        factor = min(max(bias_value, BIAS_RANGE[0]), BIAS_RANGE[1])
        if abs(factor - 1) >= 0.1:
            bias_note = f"Estimates are scaled by {factor:.2f} based on how your past tasks played out."

    estimates = [t["estimate"] for t in tasks if t["estimate"]]
    default_minutes = int(median(estimates)) if estimates else UNESTIMATED_MINUTES

    rank = {"review": 0, "progress": 1, "ready": 2}
    candidates = sorted(
        (t for t in tasks if t["status"] in rank),
        key=lambda t: (rank[t["status"]], t["lastActivity"]),
    )
    planned, used = [], 0
    for task in candidates:
        if len(planned) >= WIP_LIMIT:
            break
        base = task["estimate"] or default_minutes
        remaining = max(MIN_TASK_MINUTES, round(base * factor) - task["logged"])
        if planned and used + remaining > capacity:
            continue
        planned.append({
            "id": task["id"], "title": task["title"], "project": task["project"],
            "status": task["status"], "expectedMinutes": remaining,
            "estimated": bool(task["estimate"]),
        })
        used += remaining
    return {
        "capacityMinutes": capacity,
        "plannedMinutes": used,
        "tasks": planned,
        "basis": capacity_basis,
        "biasNote": bias_note,
        "overCapacity": bool(planned) and used > capacity,
    }


def find_resume(tasks, today_text):
    cutoff = (date.fromisoformat(today_text) - timedelta(days=STALE_DAYS)).isoformat()
    options = []
    for task in tasks:
        if task["status"] not in ("progress", "review", "ready") or task["lastActivity"] > cutoff:
            continue
        reasons, score = [], 0
        if task["status"] == "review":
            reasons.append("already in review, so it is close to done")
            score += 3
        elif task["status"] == "progress":
            reasons.append("you had already started it")
            score += 2
        if task["logged"]:
            reasons.append(f"{task['logged']} min already invested")
            score += 1
        if task["estimate"] and task["logged"] and task["logged"] < task["estimate"]:
            left = task["estimate"] - task["logged"]
            reasons.append(f"about {left} min left by your estimate")
            if left <= 60:
                score += 2
        if not reasons:
            continue
        idle = (date.fromisoformat(today_text) - date.fromisoformat(task["lastActivity"])).days
        options.append({
            "id": task["id"], "title": task["title"], "project": task["project"],
            "status": task["status"], "daysIdle": idle, "reasons": reasons, "score": score,
        })
    options.sort(key=lambda o: (-o["score"], -o["daysIdle"]))
    return options[:5]


def summarize_range(tasks, focus, downtime, start, end):
    completed = [t for t in tasks if t["status"] == "done" and t["completed"] and start <= t["completed"] <= end]
    focus_minutes = sum(m for d, m in focus if start <= d <= end)
    downtime_minutes = sum(m for d, m, _ in downtime if start <= d <= end)
    logged = focus_minutes + downtime_minutes
    return {
        "start": start,
        "end": end,
        "completed": len(completed),
        "created": sum(1 for t in tasks if start <= t["created"] <= end),
        "focusMinutes": focus_minutes,
        "downtimeMinutes": downtime_minutes,
        "daysWithFinish": len({t["completed"] for t in completed}),
        "downtimeShare": round(downtime_minutes / logged * 100) if logged else None,
        "focusPerFinished": round(focus_minutes / len(completed)) if completed else None,
    }


def build_recommendations(patterns, plan, resume, logged_days, tasks):
    recs = []
    ids = {p["id"] for p in patterns}
    open_in_flight = sum(1 for t in tasks if t["status"] in ("progress", "review"))

    if logged_days < MIN_LOGGED_DAYS:
        recs.append({
            "kind": "data",
            "title": "Log a few more days before trusting the patterns",
            "detail": f"Only {logged_days} day(s) of focus or downtime are logged in the last {HISTORY_DAYS}. Insights below are limited by this.",
        })
    if "long-days-no-finish" in ids:
        recs.append({
            "kind": "focus",
            "title": "Pick one task and define done",
            "detail": "Long days are not turning into finished work. Narrowing to a single task is likelier to help than more hours.",
        })
    if "underestimate" in ids and plan["tasks"]:
        recs.append({
            "kind": "reduce",
            "title": "Plan fewer tasks per day",
            "detail": f"Your tasks run over their estimates, so today's plan is capped at {len(plan['tasks'])} task(s) and about {plan['plannedMinutes']} min.",
        })
    if "downtime-reason" in ids:
        reason = next(p for p in patterns if p["id"] == "downtime-reason")
        recs.append({"kind": "reduce", "title": reason["title"], "detail": "Consider removing the cause or scheduling it so it stops interrupting work."})
    if "downtime-day" in ids:
        day = next(p for p in patterns if p["id"] == "downtime-day")
        recs.append({"kind": "rest", "title": day["title"], "detail": "Rather than fighting it, schedule a lighter plan or a real break on that day."})
    if open_in_flight > WIP_LIMIT:
        recs.append({
            "kind": "focus",
            "title": f"Finish before starting: {open_in_flight} tasks in flight",
            "detail": "Too many open threads dilute progress. Close the ones nearest to done first.",
        })
    if resume:
        top = resume[0]
        recs.append({
            "kind": "resume",
            "title": f"Resume \"{top['title']}\"",
            "detail": f"Idle {top['daysIdle']} days; {top['reasons'][0]}.",
        })
    if "finish-day" in ids:
        day = next(p for p in patterns if p["id"] == "finish-day")
        recs.append({"kind": "continue", "title": day["title"], "detail": "Keep that day clear of meetings and new work so finishing stays easy."})
    if not recs:
        recs.append({
            "kind": "continue",
            "title": "No issues found in your recent data",
            "detail": "Keep your current pace and keep logging so patterns can surface.",
        })
    return recs


@insights_api.get("/api/insights")
@login_required
def get_insights(user):
    today_text = parse_date(request.args.get("today")) or date.today().isoformat()
    today = date.fromisoformat(today_text)
    since = (today - timedelta(days=HISTORY_DAYS - 1)).isoformat()

    a_end = parse_date(request.args.get("aEnd")) or today_text
    a_start = parse_date(request.args.get("aStart")) or (date.fromisoformat(a_end) - timedelta(days=6)).isoformat()
    b_end = parse_date(request.args.get("bEnd")) or (date.fromisoformat(a_start) - timedelta(days=1)).isoformat()
    b_start = parse_date(request.args.get("bStart")) or (date.fromisoformat(b_end) - timedelta(days=6)).isoformat()
    for start, end in ((a_start, a_end), (b_start, b_end)):
        if start > end:
            return jsonify({"error": "A period must start on or before its end date."}), 400
        if (date.fromisoformat(end) - date.fromisoformat(start)).days >= MAX_COMPARE_DAYS:
            return jsonify({"error": f"A period can span at most {MAX_COMPARE_DAYS} days."}), 400

    data_since = min(since, a_start, b_start)
    tasks, focus, downtime, available = load_data(user["id"], data_since)
    recent_focus = [(d, m) for d, m in focus if d >= since]
    recent_downtime = [(d, m, r) for d, m, r in downtime if d >= since]

    logged_days = len({d for d, _ in recent_focus} | {d for d, _, _ in recent_downtime})
    bias_count, bias_value = estimate_bias(tasks, since)
    patterns = find_patterns(tasks, recent_focus, recent_downtime, available, since)
    plan = build_plan(tasks, recent_focus, available, bias_value, bias_count, since)
    resume = find_resume(tasks, today_text)

    return jsonify({
        "historyDays": HISTORY_DAYS,
        "loggedDays": logged_days,
        "dataLimited": logged_days < MIN_LOGGED_DAYS,
        "patterns": patterns,
        "plan": plan,
        "resume": resume,
        "compare": {
            "a": summarize_range(tasks, focus, downtime, a_start, a_end),
            "b": summarize_range(tasks, focus, downtime, b_start, b_end),
        },
        "recommendations": build_recommendations(patterns, plan, resume, logged_days, tasks),
    })
