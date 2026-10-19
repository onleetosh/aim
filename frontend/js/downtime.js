// Downtime workspace: logs entries via /api/downtime and derives simple totals locally.
import { $, escapeHtml, runAction } from "./utils.js";

let entries = [];

const rangeDays = () => Number($("#downtime-range").value);

function isoDate(date) {
  const pad = (value) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function formatMinutes(minutes) {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return hours ? `${hours}h ${rest}m` : `${rest}m`;
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

export async function loadDowntime() {
  await runAction(async () => {
    entries = (await request("/api/downtime?days=30")).entries;
    renderDowntime();
  });
}

function entriesInRange() {
  const start = new Date();
  start.setDate(start.getDate() - (rangeDays() - 1));
  const since = isoDate(start);
  return entries.filter((entry) => entry.date >= since);
}

function renderDowntime() {
  const inRange = entriesInRange();
  const total = inRange.reduce((sum, entry) => sum + entry.minutes, 0);

  $("#downtime-summary").innerHTML = [
    ["Total downtime", formatMinutes(total)],
    ["Entries", inRange.length]
  ].map(([label, value]) => `<div class="summary-card"><span>${label}</span><strong>${value}</strong></div>`).join("");

  renderChart(inRange);
  renderReasons(inRange, total);
  renderEntries(inRange);
}

function renderChart(inRange) {
  const days = rangeDays();
  const buckets = [];
  for (let offset = days - 1; offset >= 0; offset -= 1) {
    const day = new Date();
    day.setDate(day.getDate() - offset);
    buckets.push({ date: isoDate(day), minutes: 0 });
  }
  const byDate = Object.fromEntries(buckets.map((bucket) => [bucket.date, bucket]));
  inRange.forEach((entry) => { if (byDate[entry.date]) byDate[entry.date].minutes += entry.minutes; });
  const peak = Math.max(60, ...buckets.map((bucket) => bucket.minutes));
  $("#downtime-chart").innerHTML = buckets.map((bucket) => {
    const title = `${bucket.date}: ${formatMinutes(bucket.minutes)}`;
    return `<div class="bar-col" title="${title}"><div class="bar-stack"><span class="bar downtime" style="height:${(bucket.minutes / peak) * 100}%"></span></div>${days <= 7 ? `<small>${bucket.date.slice(5)}</small>` : ""}</div>`;
  }).join("");
}

function renderReasons(inRange, total) {
  const reasons = {};
  inRange.forEach((entry) => {
    const key = entry.reason || "Unspecified";
    reasons[key] = (reasons[key] || 0) + entry.minutes;
  });
  const rows = Object.entries(reasons).sort((a, b) => b[1] - a[1]);
  $("#downtime-reasons").innerHTML = rows.length
    ? rows.map(([reason, minutes]) => `<div class="reason-row"><span>${escapeHtml(reason)}</span><div class="reason-track"><span style="width:${(minutes / total) * 100}%"></span></div><strong>${formatMinutes(minutes)}</strong></div>`).join("")
    : "<p class=\"time-hint\">No downtime logged in this range.</p>";
}

function renderEntries(inRange) {
  $("#downtime-entries").innerHTML = inRange.length
    ? `<table class="time-table"><tbody>${inRange.slice(0, 20).map((entry) => `<tr><td>${entry.date}</td><td>${formatMinutes(entry.minutes)}</td><td>${escapeHtml([entry.reason, entry.note].filter(Boolean).join(" — "))}</td><td><button class="delete-project-button" type="button" data-entry-id="${entry.id}">Delete</button></td></tr>`).join("")}</tbody></table>`
    : "<p class=\"time-hint\">No entries yet.</p>";
}

export function initializeDowntime() {
  const form = $("#downtime-form");
  form.date.value = isoDate(new Date());
  $("#downtime-range").addEventListener("change", renderDowntime);

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    runAction(async () => {
      const entry = await request("/api/downtime/entries", {
        method: "POST",
        body: JSON.stringify({
          date: form.date.value,
          minutes: form.minutes.value,
          reason: form.reason.value,
          note: form.note.value
        })
      });
      entries.push(entry);
      entries.sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : b.id - a.id));
      form.minutes.value = "";
      form.reason.value = "";
      form.note.value = "";
      renderDowntime();
    });
  });

  $("#downtime-entries").addEventListener("click", (event) => {
    const button = event.target.closest("[data-entry-id]");
    if (!button) return;
    runAction(async () => {
      await request(`/api/downtime/entries/${button.dataset.entryId}`, { method: "DELETE" });
      entries = entries.filter((entry) => entry.id !== Number(button.dataset.entryId));
      renderDowntime();
    });
  });
}
