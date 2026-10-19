// Focus workspace: logs work sessions via /api/focus and derives simple totals locally.
import { state } from "./config.js";
import { loadState } from "./api.js";
import { $, escapeHtml, localDate, runAction } from "./utils.js";

let entries = [];

const rangeDays = () => Number($("#focus-range").value);

function formatMinutes(minutes) {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return hours ? `${hours}h ${rest}m` : `${rest}m`;
}

function isoDate(date) {
  const pad = (value) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

async function request(path, options) {
  const response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  if (response.status === 401) {
    window.location.reload();
    throw new Error("Your session has expired. Please log in again.");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error || "The server could not complete that request.");
  }
  return response.status === 204 ? null : response.json();
}

function fillTaskOptions() {
  const select = $("#focus-form").taskId;
  const selected = select.value;
  const options = state.tasks
    .filter((task) => task.status !== "done")
    .map((task) => {
      const project = state.projects.find((item) => item.id === task.projectId);
      return `<option value="${task.id}">${escapeHtml(task.title)}${project ? ` — ${escapeHtml(project.title)}` : ""}</option>`;
    });
  select.innerHTML = `<option value="">No specific task</option>${options.join("")}`;
  select.value = selected;
}

export async function loadFocus() {
  await runAction(async () => {
    await loadState();
    fillTaskOptions();
    entries = (await request("/api/focus?days=30")).entries;
    renderFocus();
  });
}

function entriesInRange() {
  const start = new Date();
  start.setDate(start.getDate() - (rangeDays() - 1));
  const since = isoDate(start);
  return entries.filter((entry) => entry.date >= since);
}

function renderFocus() {
  const inRange = entriesInRange();
  const total = inRange.reduce((sum, entry) => sum + entry.minutes, 0);
  $("#focus-summary").innerHTML = [
    ["Focus time", formatMinutes(total)],
    ["Sessions", inRange.length]
  ].map(([label, value]) => `<div class="summary-card"><span>${label}</span><strong>${value}</strong></div>`).join("");

  const buckets = [];
  for (let offset = rangeDays() - 1; offset >= 0; offset -= 1) {
    const day = new Date();
    day.setDate(day.getDate() - offset);
    buckets.push({ date: isoDate(day), minutes: 0 });
  }
  const byDate = Object.fromEntries(buckets.map((bucket) => [bucket.date, bucket]));
  inRange.forEach((entry) => { if (byDate[entry.date]) byDate[entry.date].minutes += entry.minutes; });
  const peak = Math.max(60, ...buckets.map((bucket) => bucket.minutes));
  $("#focus-chart").innerHTML = buckets.map((bucket) => `<div class="bar-col" title="${bucket.date}: ${formatMinutes(bucket.minutes)}"><div class="bar-stack"><span class="bar done" style="height:${(bucket.minutes / peak) * 100}%"></span></div>${rangeDays() <= 7 ? `<small>${bucket.date.slice(5)}</small>` : ""}</div>`).join("");

  $("#focus-entries").innerHTML = inRange.length
    ? `<table class="time-table"><tbody>${inRange.slice(0, 20).map((entry) => `<tr><td>${entry.date}</td><td>${formatMinutes(entry.minutes)}</td><td>${escapeHtml([entry.taskTitle, entry.note].filter(Boolean).join(" — "))}</td><td><button class="delete-project-button" type="button" data-entry-id="${entry.id}">Delete</button></td></tr>`).join("")}</tbody></table>`
    : "<p class=\"time-hint\">No sessions yet.</p>";
}

export function initializeFocus() {
  const form = $("#focus-form");
  form.date.value = localDate();
  $("#focus-range").addEventListener("change", renderFocus);

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    runAction(async () => {
      const entry = await request("/api/focus/entries", {
        method: "POST",
        body: JSON.stringify({
          date: form.date.value,
          minutes: form.minutes.value,
          taskId: form.taskId.value,
          note: form.note.value
        })
      });
      entries.push(entry);
      entries.sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : b.id - a.id));
      form.minutes.value = "";
      form.note.value = "";
      renderFocus();
    });
  });

  $("#focus-entries").addEventListener("click", (event) => {
    const button = event.target.closest("[data-entry-id]");
    if (!button) return;
    runAction(async () => {
      await request(`/api/focus/entries/${button.dataset.entryId}`, { method: "DELETE" });
      entries = entries.filter((entry) => entry.id !== Number(button.dataset.entryId));
      renderFocus();
    });
  });
}
