// Rendering functions turn application state into board and project DOM nodes.
import { statuses, state, selectedProject, detailProjectId, setSelectedProject, setDetailProjectId } from "./config.js";
import { apiRequest, loadState, moveTask } from "./api.js";
import { $, escapeHtml, runAction } from "./utils.js";
import { startDrag, initializeDragDrop } from "./drag-drop.js";

export function render() {
  // Rebuild each view from state after an API or user action changes data.
  renderProjectFilters();
  renderBoard();
  renderProjects();
  renderMomentum();
  populateProjectSelect();
  renderProjectDetail();
}

function renderProjectFilters() {
  const strip = $("#goal-strip");
  strip.innerHTML = "";
  [{ id: "all", title: "All tasks" }, ...state.projects].forEach((project) => {
    const button = document.createElement("button");
    button.className = `goal-filter${selectedProject === project.id ? " active" : ""}`;
    button.type = "button";
    button.textContent = project.title;
    button.addEventListener("click", () => { setSelectedProject(project.id); render(); });
    strip.append(button);
  });
}

function renderBoard() {
  const board = $("#board");
  board.innerHTML = "";
  statuses.forEach((status) => {
    const tasks = state.tasks.filter((task) => task.status === status.id && (selectedProject === "all" || task.projectId === selectedProject));
    if (status.id === "new") return;
    const column = document.createElement("section");
    column.className = "column";
    column.dataset.status = status.id;
    column.innerHTML = `<div class="column-header"><h3>${status.label}</h3><span class="count">${tasks.length}</span></div><div class="column-body"></div>`;
    initializeDragDrop(column, status.id);
    const body = column.querySelector(".column-body");
    if (!tasks.length) body.append($("#empty-state-template").content.cloneNode(true));
    tasks.forEach((task) => body.append(createTaskCard(task)));
    board.append(column);
  });
}

export function createTaskCard(task) {
  // Cards are rebuilt after state changes so status and project labels stay current.
  const card = document.createElement("article");
  const project = state.projects.find((item) => item.id === task.projectId);
  const nextStatus = statuses[Math.min(statuses.findIndex((item) => item.id === task.status) + 1, statuses.length - 1)];
  card.className = "task-card";
  card.draggable = false;
  card.dataset.taskId = task.id;
  card.addEventListener("pointerdown", (event) => startDrag(event, card, task.id, "pointer"));
  card.addEventListener("mousedown", (event) => startDrag(event, card, task.id, "mouse"));
  card.innerHTML = `<h3>${escapeHtml(task.title)}</h3>${task.description ? `<p>${escapeHtml(task.description)}</p>` : ""}<div class="task-meta"><span>${project ? escapeHtml(project.title) : "No project"}</span><span>${task.status === "done" ? "Complete" : ""}</span></div><div class="task-actions">${task.status !== "done" ? `<button type="button" data-next="${task.id}">Move to ${nextStatus.label}</button>` : ""}<button type="button" data-delete="${task.id}" aria-label="Delete ${escapeHtml(task.title)}">Delete</button></div>`;
  card.querySelector("[data-next]")?.addEventListener("click", async () => runAction(() => moveTask(task.id, nextStatus.id)));
  card.querySelector("[data-delete]").addEventListener("click", async () => runAction(async () => {
    await apiRequest(`/api/tasks/${task.id}`, { method: "DELETE" });
    await loadState();
  }));
  return card;
}

function renderProjects() {
  const grid = $("#goals-grid");
  grid.innerHTML = "";
  state.projects.forEach((project) => {
    const tasks = state.tasks.filter((task) => task.projectId === project.id);
    const completed = tasks.filter((task) => task.status === "done").length;
    const percent = tasks.length ? Math.round((completed / tasks.length) * 100) : 0;
    const card = document.createElement("article");
    card.className = "goal-card project-card";
    card.tabIndex = 0;
    card.setAttribute("role", "button");
    card.setAttribute("aria-label", `Open ${project.title} project`);
    card.innerHTML = `<h3>${escapeHtml(project.title)}</h3><p>${escapeHtml(project.description || "A project without a description. Start with one small step.")}</p><div class="goal-progress"><span>${completed} of ${tasks.length} tasks complete</span><strong>${percent}%</strong></div><div class="progress-track"><span style="width:${percent}%"></span></div><div class="project-actions"><button type="button" class="delete-project-button" data-delete-project="${project.id}">Delete project</button></div>`;
    card.addEventListener("click", () => openProject(project.id));
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openProject(project.id); }
    });
    card.querySelector("[data-delete-project]").addEventListener("click", async (event) => {
      event.stopPropagation();
      if (!window.confirm(`Delete "${project.title}" and all of its tasks?`)) return;
      await runAction(async () => {
        await apiRequest(`/api/projects/${project.id}`, { method: "DELETE" });
        if (detailProjectId === project.id) {
          setDetailProjectId(null);
          showView("goals");
        }
        setSelectedProject("all");
        await loadState();
      });
    });
    grid.append(card);
  });
  if (!state.projects.length) grid.innerHTML = '<div class="empty-state"><span class="empty-icon">◎</span><h3>Start with a project</h3><p>A clear destination makes the next step easier to see.</p></div>';
}

function openProject(projectId) {
  setDetailProjectId(projectId);
  setSelectedProject(projectId);
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.remove("active"));
  render();
  showView("project-detail");
}

function renderProjectDetail() {
  const project = state.projects.find((item) => item.id === detailProjectId);
  if (!project) return;
  const tasks = state.tasks.filter((task) => task.projectId === project.id);
  const groups = [
    { label: "New", description: "Tasks waiting to be started.", statuses: ["new"] },
    { label: "Active", description: "Tasks currently moving through the board.", statuses: ["ready", "progress", "review"] },
    { label: "Complete", description: "Tasks finished.", statuses: ["done"] }
  ];
  $("#project-detail-heading").textContent = project.title;
  $("#project-detail-description").textContent = project.description || "No project description yet.";
  $("#project-summary").innerHTML = groups.map((group) => `<div class="summary-card"><span>${group.label}</span><strong>${tasks.filter((task) => group.statuses.includes(task.status)).length}</strong></div>`).join("");
  const container = $("#project-task-groups");
  container.innerHTML = "";
  groups.forEach((group) => {
    const groupTasks = tasks.filter((task) => group.statuses.includes(task.status));
    const section = document.createElement("section");
    section.className = "project-task-group";
    section.dataset.group = group.label.toLowerCase();
    section.innerHTML = `<div class="project-group-heading"><div><h3>${group.label}</h3><p>${group.description}</p></div><span class="count">${groupTasks.length}</span></div><div class="project-group-tasks"></div>`;
    initializeDragDrop(section, group.label === "New" ? "new" : group.label === "Active" ? "ready" : "done");
    const taskContainer = section.querySelector(".project-group-tasks");
    if (!groupTasks.length) taskContainer.innerHTML = "<p class=\"project-empty\">No tasks in this group.</p>";
    groupTasks.forEach((task) => taskContainer.append(createTaskCard(task)));
    container.append(section);
  });
}

export function showView(view) {
  $("#board-view").classList.toggle("hidden", view !== "board");
  $("#goals-view").classList.toggle("hidden", view !== "goals");
  $("#project-detail-view").classList.toggle("hidden", view !== "project-detail");
}

function renderMomentum() {
  const total = state.tasks.length;
  const complete = state.tasks.filter((task) => task.status === "done").length;
  const percent = total ? Math.round((complete / total) * 100) : 0;
  $("#momentum-percent").textContent = `${percent}%`;
  $("#momentum-bar").style.width = `${percent}%`;
  $("#completed-count").textContent = complete;
  $("#total-count").textContent = total;
}

function populateProjectSelect() {
  $("#task-goal").innerHTML = state.projects.length
    ? state.projects.map((project) => `<option value="${project.id}">${escapeHtml(project.title)}</option>`).join("")
    : "<option value=\"\">No project yet</option>";
}
