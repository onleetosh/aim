// Form dialogs are kept separate from the board and project renderers.
import { apiRequest, loadState } from "./api.js";
import { setSelectedProject, detailProjectId, state } from "./config.js";
import { $, escapeHtml, localDate, runAction } from "./utils.js";

export function openTaskModal(projectId) {
  $("#task-form").reset();
  $("#task-id").value = "";
  const projectSelect = $("#task-project");
  projectSelect.innerHTML = state.projects.map((project) => `<option value="${project.id}">${escapeHtml(project.title)}</option>`).join("");
  if (!state.projects.length) {
    runAction(async () => { throw new Error("Create a project before adding a task."); });
    return;
  }
  projectSelect.value = projectId || state.projects[0].id;
  $("#task-project-label").hidden = !projectId;
  projectSelect.hidden = !projectId;
  $("#task-modal-eyebrow").textContent = "Break it down";
  $("#task-modal-heading").textContent = "New task";
  $("#task-submit").textContent = "Add task";
  $("#task-modal").showModal();
  $("#task-title").focus();
}

export function openEditTaskModal(task) {
  $("#task-form").reset();
  $("#task-id").value = task.id;
  $("#task-project").innerHTML = state.projects.map((project) => `<option value="${project.id}">${escapeHtml(project.title)}</option>`).join("");
  $("#task-project").value = task.projectId;
  $("#task-project-label").hidden = true;
  $("#task-project").hidden = true;
  $("#task-title").value = task.title;
  $("#task-description").value = task.description || "";
  $("#task-estimate").value = task.estimateMinutes || "";
  $("#task-modal-eyebrow").textContent = "Make it clearer";
  $("#task-modal-heading").textContent = "Edit task";
  $("#task-submit").textContent = "Save changes";
  $("#task-modal").showModal();
  $("#task-title").focus();
}

export function openGoalModal() {
  $("#goal-form").reset();
  $("#goal-modal").showModal();
  $("#goal-title").focus();
}

export function initializeModals() {
  $("#goals-new-button").addEventListener("click", openGoalModal);
  document.querySelectorAll("[data-close]").forEach((button) => button.addEventListener("click", () => $(`#${button.dataset.close}`).close()));
  $("#project-new-task-button").addEventListener("click", () => openTaskModal(detailProjectId));
  $("#task-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const dialog = formElement.closest("dialog");
    const taskId = form.get("taskId");
    const fields = {
      title: form.get("title"),
      description: form.get("description"),
      estimateMinutes: form.get("estimateMinutes"),
      today: localDate()
    };
    await runAction(async () => {
      if (taskId) {
        await apiRequest(`/api/tasks/${taskId}`, { method: "PATCH", body: JSON.stringify(fields) });
      } else {
        await apiRequest("/api/tasks", { method: "POST", body: JSON.stringify({ ...fields, projectId: form.get("project") }) });
      }
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
}
