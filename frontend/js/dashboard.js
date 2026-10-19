// Dashboard: renders the summary computed by /api/dashboard.
import { $, escapeHtml, localDate, runAction } from "./utils.js";
import { openGoalModal, openTaskModal } from "./modals.js";

const STATUS_LABELS = { new: "New", ready: "Ready", progress: "In progress", review: "Review", done: "Done" };

export async function loadDashboard() {
  await runAction(async () => {
    const response = await fetch(`/api/dashboard?today=${localDate()}`);
    if (response.status === 401) {
      window.location.reload();
      return;
    }
    if (!response.ok) throw new Error("The dashboard could not be loaded.");
    renderDashboard(await response.json());
  });
}

function renderDashboard({ recommendation, priorities, overview, intention, action, momentum, awareness, focus, planAccuracy, accounting }) {
  $("#dash-overview").innerHTML = [
    ["Active projects", `${overview.activeProjects} of ${overview.totalProjects}`],
    ["Active progress", `${overview.activePercent}%`],
    ["Done this week", momentum.completedThisWeek],
    ["Downtime this week", `${awareness.downtime.totalMinutes}m`]
  ].map(([label, value]) => `<div class="summary-card"><span>${label}</span><strong>${value}</strong></div>`).join("");

  $("#dash-priorities").innerHTML = priorities.length
    ? priorities.map((task, index) => `<div class="stale-row"><span>${index + 1}. ${escapeHtml(task.title)} <small>${escapeHtml(task.project)}</small></span><strong>${task.why}</strong></div>`).join("")
    : "<p class=\"time-hint\">No open tasks to prioritize. Add or move a task to Ready.</p>";

  $("#dash-recommendation").className = `recommendation ${recommendation.kind}`;
  $("#dash-recommendation").innerHTML = `
    <p class="eyebrow">Suggested next move</p>
    <h3>${escapeHtml(recommendation.headline)}</h3>
    ${recommendation.reasons.map((reason) => `<p>${escapeHtml(reason)}</p>`).join("")}
    <small>Based on your goals, tasks and logged time. More hours are not the goal; fit between effort and progress is.</small>`;

  $("#dash-intention").innerHTML = intention.projects.length
    ? `<p class="time-hint">${intention.moving} of ${intention.open} open project(s) moving.</p>` + intention.projects.map((project) => `
        <div class="dash-project">
          <div class="dash-project-head"><strong>${escapeHtml(project.title)}</strong><span class="dash-tag ${project.label.replace(/\s+/g, "-").toLowerCase()}">${project.label}</span></div>
          <div class="reason-track"><span class="done-fill" style="width:${project.percent}%"></span></div>
          <small>${project.done} of ${project.total} tasks done</small>
        </div>`).join("")
    : "<p class=\"time-hint\">No projects yet. Create one to state what you are working toward.</p>";

  const { counts } = action;
  $("#dash-action").innerHTML = `
    <div class="dash-stats">
      <div class="summary-card"><span>Completion rate</span><strong>${action.completionRate}%</strong></div>
      <div class="summary-card"><span>Done this week</span><strong>${momentum.completedThisWeek}</strong></div>
    </div>
    <div class="dash-status-row">${Object.keys(STATUS_LABELS).map((status) => `<div><strong>${counts[status]}</strong><small>${STATUS_LABELS[status]}</small></div>`).join("")}</div>
    ${action.stale.count ? `<h4>Stale: no change in ${action.stale.days}+ days (${action.stale.count})</h4>` + action.stale.tasks.map((task) => `<div class="stale-row"><span>${escapeHtml(task.title)} <small>${escapeHtml(task.project)}</small></span><strong>${task.daysIdle}d</strong></div>`).join("") : "<p class=\"time-hint\">No stale tasks.</p>"}`;

  const peak = Math.max(1, ...momentum.history.map((day) => day.completed));
  $("#dash-momentum").innerHTML = `
    <div class="dash-stats">
      <div class="summary-card"><span>Momentum score</span><strong>${momentum.percent}%</strong></div>
      <div class="summary-card"><span>Active days (last ${momentum.windowDays})</span><strong>${momentum.activeDays}</strong></div>
      <div class="summary-card"><span>Current streak</span><strong>${momentum.streak}</strong></div>
    </div>
    <div class="time-chart">${momentum.history.map((day) => `<div class="bar-col" title="${day.date}: ${day.completed} finished"><div class="bar-stack"><span class="bar done" style="height:${(day.completed / peak) * 100}%"></span></div></div>`).join("")}</div>
    <p class="time-hint">Momentum score = days in the last ${momentum.windowDays} with at least one finished task. Chart shows tasks finished per day over 14 days.</p>`;

  const { downtime, insights } = awareness;
  $("#dash-awareness").innerHTML = `
    <div class="dash-insights">${insights.length
      ? insights.map((item) => `<div class="dash-insight ${item.kind}"><span>${{ help: "Helping", hinder: "Hindering", next: "Next step" }[item.kind]}</span><p>${escapeHtml(item.text)}</p></div>`).join("")
      : "<p class=\"time-hint\">Nothing to flag yet. Finish a task or log downtime to see insights.</p>"}</div>
    ${downtime.reasons.length ? `<h4>Downtime this week: ${downtime.totalMinutes} min</h4>` + downtime.reasons.map((item) => `<div class="reason-row"><span>${escapeHtml(item.reason)}</span><div class="reason-track"><span style="width:${(item.minutes / downtime.totalMinutes) * 100}%"></span></div><strong>${item.minutes}m · ${item.share}%</strong></div>`).join("") : "<p class=\"time-hint\">No downtime logged this week.</p>"}`;

  $("#dash-plan").innerHTML = planAccuracy.taskCount
    ? `<div class="dash-stats">
        <div class="summary-card"><span>Actual vs estimate</span><strong>${planAccuracy.percent}%</strong></div>
        <div class="summary-card"><span>Tasks measured</span><strong>${planAccuracy.taskCount}</strong></div>
      </div>
      ${planAccuracy.tasks.map((task) => `<div class="stale-row"><span>${escapeHtml(task.title)}</span><strong>${task.logged}m / ${task.estimate}m</strong></div>`).join("")}
      <p class="time-hint">100% means finished tasks took exactly as long as estimated. ${planAccuracy.finishedWithoutData} finished task(s) lack an estimate or logged sessions and are excluded.</p>`
    : "<p class=\"time-hint\">Add an estimate to a task, log work sessions against it in Focus, and finish it to see accuracy here.</p>";

  const { availableMinutes: total, focusMinutes, downtimeMinutes, unrecordedMinutes } = accounting;
  const share = (value) => (total ? Math.min(100, (value / total) * 100) : 0);
  $("#dash-accounting").innerHTML = `
    <div class="account-bar" role="img" aria-label="Focus, downtime, and unrecorded time this week">
      <span class="focus" style="width:${share(focusMinutes)}%"></span>
      <span class="downtime" style="width:${share(downtimeMinutes)}%"></span>
    </div>
    <p class="time-legend"><span class="dot productive"></span> Focus ${focusMinutes}m <span class="dot downtime"></span> Downtime ${downtimeMinutes}m <span class="dot unrecorded"></span> Unrecorded ${unrecordedMinutes}m (${accounting.unrecordedPercent}%)</p>
    <p class="time-hint">Based on ${accounting.availablePerDay / 60}h available per day for the last 7 days. Unrecorded time is not counted as downtime or focus; it is simply not logged. Days with any log: ${accounting.daysWithAnyLog} of 7.</p>`;
  $("#available-form").hours.value = accounting.availablePerDay / 60;
}

export function initializeDashboard() {
  $("#dashboard-new-task-button").addEventListener("click", () => openTaskModal(null));
  $("#dashboard-new-project-button").addEventListener("click", openGoalModal);
  $("#available-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const hours = Number(event.currentTarget.hours.value);
    runAction(async () => {
      const response = await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ availableMinutesPerDay: Math.round(hours * 60) })
      });
      if (!response.ok) throw new Error((await response.json().catch(() => ({}))).error || "Could not save the setting.");
      await loadDashboard();
    });
  });
}
