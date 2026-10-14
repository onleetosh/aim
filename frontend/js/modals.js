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
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const dialog = formElement.closest("dialog");
    await runAction(async () => {
      await apiRequest("/api/tasks", { method: "POST", body: JSON.stringify({ title: form.get("title"), description: form.get("description"), projectId: form.get("project") }) });
      dialog.close();
      await loadState();
    });
  });
  $("#goal-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const dialog = formElement.closest("dialog");
    await runAction(async () => {
      const project = await apiRequest("/api/projects", { method: "POST", body: JSON.stringify({ title: form.get("title"), description: form.get("description") }) });
      setSelectedProject(project.id);
      dialog.close();
      await loadState();
    });
  });
  document.addEventListener("click", (event) => {
    if (event.target instanceof Element && event.target.matches('[data-action="new-task"]')) {
      openTaskModal();
    }
  });
}
