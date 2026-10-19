// Analytics: renders /api/analytics (trends, planned vs actual, downtime patterns, stalled work).
import { $, escapeHtml, localDate, runAction } from "./utils.js";

function formatMinutes(minutes) {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return hours ? `${hours}h ${rest}m` : `${rest}m`;
}

export async function loadAnalytics() {
  await runAction(async () => {
    const period = $("#analytics-period").value;
    const response = await fetch(`/api/analytics?period=${period}&today=${localDate()}`);
    if (response.status === 401) {
      window.location.reload();
      return;
    }
    if (!response.ok) throw new Error("Analytics could not be loaded.");
    renderAnalytics(await response.json());
  });
}

function bars(items, valueOf, className, titleOf, showLabels) {
  const peak = Math.max(1, ...items.map(valueOf));
  return items.map((item) => `<div class="bar-col" title="${escapeHtml(titleOf(item))}"><div class="bar-stack"><span class="bar ${className}" style="height:${(valueOf(item) / peak) * 100}%"></span></div>${showLabels ? `<small>${escapeHtml(item.label)}</small>` : ""}</div>`).join("");
}

function deltaText(value, unit, lowerIsBetter) {
  if (value === 0) return "no change";
  const better = lowerIsBetter ? value < 0 : value > 0;
  const text = `${value > 0 ? "+" : "−"}${unit === "min" ? formatMinutes(Math.abs(value)) : Math.abs(value)}`;
  return `<span class="${better ? "delta-good" : "delta-warn"}">${text}</span>`;
}

function renderAnalytics(data) {
  const { trend, comparison, planVsActual, downtimePatterns, stalled } = data;
  const unit = data.period === "monthly" ? "month" : "week";
  const labels = trend.length <= 8;

  $("#analytics-comparison").innerHTML = [
    ["Completed", comparison.completed.current, deltaText(comparison.completed.delta, "", false)],
    ["Focus", formatMinutes(comparison.focusMinutes.current), deltaText(comparison.focusMinutes.delta, "min", false)],
    ["Downtime", formatMinutes(comparison.downtimeMinutes.current), deltaText(comparison.downtimeMinutes.delta, "min", true)]
  ].map(([label, value, delta]) => `<div class="summary-card"><span>${label} this ${unit}</span><strong>${value}</strong><small>${delta} vs last ${unit}</small></div>`).join("");

  $("#analytics-completed").innerHTML = bars(trend, (b) => b.completed, "done", (b) => `${b.label}: ${b.completed} completed, ${b.created} created`, labels);
  $("#analytics-rate").innerHTML = bars(trend, (b) => b.completionRate || 0, "done", (b) => `${b.label}: ${b.completionRate === null ? "no tasks in play" : `${b.completionRate}% (${b.completed} of ${b.inPlay})`}`, labels);

  const peak = Math.max(60, ...trend.map((b) => Math.max(b.focusMinutes, b.downtimeMinutes)));
  $("#analytics-time").innerHTML = trend.map((b) => `<div class="bar-col" title="${escapeHtml(b.label)}: focus ${formatMinutes(b.focusMinutes)}, downtime ${formatMinutes(b.downtimeMinutes)}"><div class="bar-pair"><span class="bar done" style="height:${(b.focusMinutes / peak) * 100}%"></span><span class="bar downtime" style="height:${(b.downtimeMinutes / peak) * 100}%"></span></div>${labels ? `<small>${escapeHtml(b.label)}</small>` : ""}</div>`).join("");

  const withPlan = trend.filter((b) => b.measuredTasks);
  $("#analytics-plan").innerHTML = withPlan.length
    ? `<div class="dash-stats">
        <div class="summary-card"><span>Planned</span><strong>${formatMinutes(planVsActual.plannedMinutes)}</strong></div>
        <div class="summary-card"><span>Actual</span><strong>${formatMinutes(planVsActual.actualMinutes)}</strong></div>
      </div>
      ${withPlan.map((b) => `<div class="stale-row"><span>${escapeHtml(b.label)} <small>${b.measuredTasks} task(s)</small></span><strong>${formatMinutes(b.actualMinutes)} / ${formatMinutes(b.plannedMinutes)}</strong></div>`).join("")}
      <p class="time-hint">Only finished tasks with both an estimate and logged sessions, grouped by the period they were finished.</p>`
    : "<p class=\"time-hint\">Estimate tasks, log sessions in Focus, and finish them to compare plan and reality.</p>";

  if (!downtimePatterns.totalMinutes) {
    $("#analytics-patterns").innerHTML = "<p class=\"time-hint\">No downtime logged in this range.</p>";
  } else {
    const cellMax = Math.max(1, ...downtimePatterns.categories.flatMap((c) => c.byWeekday));
    $("#analytics-patterns").innerHTML = `
      <p class="time-hint">Peak day: <strong>${downtimePatterns.peakWeekday}</strong>. Total ${formatMinutes(downtimePatterns.totalMinutes)} over the range.</p>
      <table class="heat-table"><thead><tr><th></th>${downtimePatterns.weekdays.map((day) => `<th>${day}</th>`).join("")}<th>Total</th></tr></thead><tbody>
      ${downtimePatterns.categories.map((c) => `<tr><th>${escapeHtml(c.category)} <small>${c.share}%</small></th>${c.byWeekday.map((m) => `<td style="--heat:${m / cellMax}">${m || ""}</td>`).join("")}<td>${formatMinutes(c.minutes)}</td></tr>`).join("")}
      <tr class="heat-total"><th>All</th>${downtimePatterns.byWeekday.map((m) => `<td>${m || ""}</td>`).join("")}<td>${formatMinutes(downtimePatterns.totalMinutes)}</td></tr>
      </tbody></table>`;
  }

  $("#analytics-stalled").innerHTML = stalled.projects.length || stalled.tasks.length
    ? `${stalled.projects.length ? `<h4>Projects with no activity for ${data.staleDays}+ days</h4>` + stalled.projects.map((p) => `<div class="stale-row"><span>${escapeHtml(p.title)} <small>${p.openTasks} open</small></span><strong>${p.daysIdle}d</strong></div>`).join("") : ""}
       ${stalled.tasks.length ? `<h4>Stalled tasks (${stalled.taskCount})</h4>` + stalled.tasks.map((t) => `<div class="stale-row"><span>${escapeHtml(t.title)} <small>${escapeHtml(t.project)} · ${t.status}</small></span><strong>${t.daysIdle}d</strong></div>`).join("") : ""}`
    : "<p class=\"time-hint\">Nothing has stalled.</p>";
}

export function initializeAnalytics() {
  $("#analytics-period").addEventListener("change", loadAnalytics);
}
