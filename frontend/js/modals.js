// Form dialogs are kept separate from the board and project renderers.
import { apiRequest, loadState } from "./api.js";
import { setSelectedProject, detailProjectId } from "./config.js";
import { $, runAction } from "./utils.js";

export function openTaskModal(projectId = null) {
  $("#task-form").reset();
  if (projectId) $("#task-goal").value = projectId;
  $("#task-modal").showModal();
  $("#task-title").focus();
}

function openGoalModal() {
  $("#goal-form").reset();
  $("#goal-modal").showModal();
  $("#goal-title").focus();
}

export function initializeModals() {
  $("#new-task-button").addEventListener("click", openTaskModal);
  $("#new-goal-button").addEventListener("click", openGoalModal);
  $("#goals-new-button").addEventListener("click", openGoalModal);
  document.querySelectorAll("[data-close]").forEach((button) => button.addEventListener("click", () => $(`#${button.dataset.close}`).close()));
  $("#project-new-task-button").addEventListener("click", () => openTaskModal(detailProjectId));
  $("#task-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await runAction(async () => {
      await apiRequest("/api/tasks", { method: "POST", body: JSON.stringify({ title: form.get("title"), description: form.get("description"), projectId: form.get("project") }) });
      event.currentTarget.closest("dialog").close();
      await loadState();
    });
  });
  $("#goal-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await runAction(async () => {
      const project = await apiRequest("/api/projects", { method: "POST", body: JSON.stringify({ title: form.get("title"), description: form.get("description") }) });
      setSelectedProject(project.id);
      event.currentTarget.closest("dialog").close();
      await loadState();
    });
  });
  document.addEventListener("click", (event) => {
    if (event.target instanceof Element && event.target.matches('[data-action="new-task"]')) {
      openTaskModal();
    }
  });
}
