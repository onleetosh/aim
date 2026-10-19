// Frontend entry point: connect navigation, forms, and the initial data load.
import { loadState } from "./api.js";
import { setDetailProjectId } from "./config.js";
import { showView } from "./render.js";
import { initializeModals } from "./modals.js";
import { initializeDowntime, loadDowntime } from "./downtime.js";
import { loadDashboard, initializeDashboard } from "./dashboard.js";
import { initializeFocus, loadFocus } from "./focus.js";
import { initializeAnalytics, loadAnalytics } from "./analytics.js";
import { initializeInsights, loadInsights } from "./insights.js";

document.querySelectorAll(".nav-item").forEach((button) => button.addEventListener("click", () => {
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.remove("active"));
  button.classList.add("active");
  setDetailProjectId(null);
  showView(button.dataset.view);
  if (button.dataset.view === "focus") {
    loadFocus();
    loadDowntime();
  }
  if (button.dataset.view === "dashboard") loadDashboard();
  if (button.dataset.view === "analytics") {
    loadAnalytics();
    loadInsights();
  }
}));
document.querySelector("#back-to-projects").addEventListener("click", () => {
  setDetailProjectId(null);
  showView("goals");
});

document.querySelector("#logout-button").addEventListener("click", async () => {
  await fetch("/api/auth/logout", { method: "POST" });
  window.location.reload();
});

initializeModals();
initializeDowntime();
initializeFocus();
initializeDashboard();
initializeAnalytics();
initializeInsights();
loadState();
