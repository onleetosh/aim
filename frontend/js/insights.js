// Insights: renders /api/insights (patterns, daily plan, resume list, comparison, recommendations).
import { $, escapeHtml, localDate, runAction } from "./utils.js";

const KIND_LABELS = { focus: "Focus", reduce: "Reduce", rest: "Rest", continue: "Continue", resume: "Resume", data: "Data", plan: "Plan" };

function formatMinutes(minutes) {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return hours ? `${hours}h ${rest}m` : `${rest}m`;
}

function shiftDate(day, offset) {
  const [year, month, date] = day.split("-").map(Number);
  const shifted = new Date(year, month - 1, date + offset);
  return localDate(shifted);
}

function setDefaultRanges() {
  const today = localDate();
  const aStart = shiftDate(today, -6);
  const bEnd = shiftDate(aStart, -1);
  $("#compare-a-start").value = aStart;
  $("#compare-a-end").value = today;
  $("#compare-b-start").value = shiftDate(bEnd, -6);
  $("#compare-b-end").value = bEnd;
}

export async function loadInsights() {
  await runAction(async () => {
    const params = new URLSearchParams({
      today: localDate(),
      aStart: $("#compare-a-start").value,
      aEnd: $("#compare-a-end").value,
      bStart: $("#compare-b-start").value,
      bEnd: $("#compare-b-end").value
    });
    const response = await fetch(`/api/insights?${params}`);
    if (response.status === 401) {
      window.location.reload();
      return;
    }
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Insights could not be loaded.");
    renderInsights(data);
  });
}

function compareRow(label, a, b, format, lowerIsBetter) {
  if (a === null || b === null) {
    return `<tr><th>${label}</th><td>${a === null ? "–" : format(a)}</td><td>${b === null ? "–" : format(b)}</td><td>–</td></tr>`;
  }
  const delta = a - b;
  const better = lowerIsBetter ? delta < 0 : delta > 0;
  const text = delta === 0 ? "no change" : `<span class="${better ? "delta-good" : "delta-warn"}">${delta > 0 ? "+" : "−"}${format(Math.abs(delta))}</span>`;
  return `<tr><th>${label}</th><td>${format(a)}</td><td>${format(b)}</td><td>${text}</td></tr>`;
}

function renderInsights(data) {
  $("#insights-limit").textContent = data.dataLimited
    ? `Limited data: only ${data.loggedDays} day(s) with focus or downtime logged in the last ${data.historyDays}. Treat these insights as tentative.`
    : `Based on the last ${data.historyDays} days (${data.loggedDays} days with logged time).`;

  $("#insights-recommendations").innerHTML = data.recommendations.map((rec) => `
    <div class="recommendation ${rec.kind}"><p class="eyebrow">${KIND_LABELS[rec.kind] || "Suggestion"}</p><h3>${escapeHtml(rec.title)}</h3><p>${escapeHtml(rec.detail)}</p></div>`).join("");

  const plan = data.plan;
  $("#insights-plan").innerHTML = plan.tasks.length
    ? `<p class="time-hint">Capacity about <strong>${formatMinutes(plan.capacityMinutes)}</strong>. ${escapeHtml(plan.basis)}${plan.biasNote ? " " + escapeHtml(plan.biasNote) : ""}</p>
       ${plan.tasks.map((t) => `<div class="stale-row"><span>${escapeHtml(t.title)} <small>${escapeHtml(t.project)} · ${t.status}${t.estimated ? "" : " · no estimate"}</small></span><strong>${formatMinutes(t.expectedMinutes)}</strong></div>`).join("")}
       <p class="time-hint">Total ${formatMinutes(plan.plannedMinutes)}${plan.overCapacity ? " — more than your capacity; consider splitting the first task." : "."}</p>`
    : "<p class=\"time-hint\">No open tasks are ready to plan. Move a task to Ready or In progress.</p>";

  $("#insights-resume").innerHTML = data.resume.length
    ? data.resume.map((t) => `<div class="stale-row"><span>${escapeHtml(t.title)} <small>${escapeHtml(t.project)} · ${escapeHtml(t.reasons.join("; "))}</small></span><strong>${t.daysIdle}d idle</strong></div>`).join("")
    : "<p class=\"time-hint\">No idle tasks with a good reason to resume.</p>";

  $("#insights-patterns").innerHTML = data.patterns.length
    ? data.patterns.map((p) => `<div class="stale-row"><span><strong>${escapeHtml(p.title)}</strong><small>${escapeHtml(p.detail)}</small></span></div>`).join("")
    : "<p class=\"time-hint\">No recurring patterns yet. Patterns appear after a few weeks of finishing tasks and logging time.</p>";

  const { a, b } = data.compare;
  $("#insights-compare").innerHTML = `
    <table class="time-table"><thead><tr><th></th><th>A: ${a.start} → ${a.end}</th><th>B: ${b.start} → ${b.end}</th><th>A vs B</th></tr></thead><tbody>
      ${compareRow("Tasks completed", a.completed, b.completed, String, false)}
      ${compareRow("Tasks created", a.created, b.created, String, true)}
      ${compareRow("Days with a finish", a.daysWithFinish, b.daysWithFinish, String, false)}
      ${compareRow("Focus time", a.focusMinutes, b.focusMinutes, formatMinutes, false)}
      ${compareRow("Downtime", a.downtimeMinutes, b.downtimeMinutes, formatMinutes, true)}
      ${compareRow("Downtime share", a.downtimeShare, b.downtimeShare, (v) => `${v}%`, true)}
      ${compareRow("Focus per finished task", a.focusPerFinished, b.focusPerFinished, formatMinutes, true)}
    </tbody></table>
    <p class="time-hint">More focus time is not automatically better; compare it with what was finished.</p>`;
}

export function initializeInsights() {
  setDefaultRanges();
  $("#compare-form").addEventListener("submit", (event) => {
    event.preventDefault();
    loadInsights();
  });
}
