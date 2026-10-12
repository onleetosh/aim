const statuses = [
  { id: "new", label: "New" },
  { id: "ready", label: "Ready" },
  { id: "progress", label: "In progress" },
  { id: "review", label: "Review" },
  { id: "done", label: "Done" }
];

let state = { projects: [], tasks: [] };
let selectedProject = "all";
let detailProjectId = null;
let pointerDrag = null;
let mouseDrag = null;
const LOCAL_STORAGE_KEY = "aim-file-mode-state";
const fileMode = window.location.protocol === "file:";

const $ = (selector) => document.querySelector(selector);

async function apiRequest(path, options = {}) {
  if (fileMode) return localRequest(path, options);
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error || "The server could not complete that request.");
  }

  return response.status === 204 ? null : response.json();
}

function localRequest(path, options = {}) {
  const stored = localStorage.getItem(LOCAL_STORAGE_KEY);
  const localState = stored ? JSON.parse(stored) : {
    projects: [
      { id: "local-project-coursework", title: "Finish coursework", description: "Keep the semester moving forward." },
      { id: "local-project-aim", title: "Build A.I.M.", description: "Turn the idea into a useful first version." }
    ],
    tasks: []
  };
  const body = options.body ? JSON.parse(options.body) : {};
  const projectMatch = path.match(/^\/api\/projects\/([^/]+)$/);
  const taskMatch = path.match(/^\/api\/tasks\/([^/]+)$/);

  if (path === "/api/state") return localState;
  if (path === "/api/projects" && (!options.method || options.method === "POST")) {
    const project = { id: `local-project-${Date.now()}`, title: String(body.title).trim(), description: String(body.description || "").trim() };
    if (!project.title) throw new Error("Project title is required.");
    localState.projects.push(project);
    saveLocalState(localState);
    return project;
  }
  if (path === "/api/tasks" && options.method === "POST") {
    const task = { id: `local-task-${Date.now()}`, projectId: String(body.projectId), title: String(body.title).trim(), description: String(body.description || "").trim(), status: "new" };
    if (!task.title || !localState.projects.some((project) => project.id === task.projectId)) throw new Error("Task title and project are required.");
    localState.tasks.push(task);
    saveLocalState(localState);
    return task;
  }
  if (taskMatch && options.method === "PATCH") {
    const task = localState.tasks.find((item) => item.id === taskMatch[1]);
    if (!task) throw new Error("Task not found.");
    task.status = body.status;
    saveLocalState(localState);
    return task;
  }
  if (taskMatch && options.method === "DELETE") {
    localState.tasks = localState.tasks.filter((task) => task.id !== taskMatch[1]);
    saveLocalState(localState);
    return null;
  }
  if (projectMatch) throw new Error("Project not found.");
  throw new Error("The local browser storage request was not recognized.");
}

function saveLocalState(localState) {
  localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(localState));
}

async function loadState() {
  try {
    state = await apiRequest("/api/state");
    render();
  } catch (error) {
    showError(error);
  }
}

function render() {
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
    button.addEventListener("click", () => { selectedProject = project.id; render(); });
    strip.append(button);
  });
}

function renderBoard() {
  const board = $("#board");
  board.innerHTML = "";
  statuses.forEach((status) => {
    const tasks = state.tasks.filter((task) => task.status === status.id
      && (selectedProject === "all" || task.projectId === selectedProject));
    if (status.id === "new") return;
    const column = document.createElement("section");
    column.className = "column";
    column.dataset.status = status.id;
    column.addEventListener("dragover", (event) => {
      event.preventDefault();
      column.classList.add("drop-target");
    });
    column.addEventListener("dragleave", () => column.classList.remove("drop-target"));
    column.addEventListener("drop", async (event) => {
      event.preventDefault();
      column.classList.remove("drop-target");
      const taskId = event.dataTransfer.getData("text/plain");
      await moveTask(taskId, status.id);
    });
    column.innerHTML = `<div class="column-header"><h3>${status.label}</h3><span class="count">${tasks.length}</span></div><div class="column-body"></div>`;
    const body = column.querySelector(".column-body");
    if (!tasks.length) body.append($("#empty-state-template").content.cloneNode(true));
    tasks.forEach((task) => body.append(createTaskCard(task)));
    board.append(column);
  });
}

function createTaskCard(task) {
  const card = document.createElement("article");
  const project = state.projects.find((item) => item.id === task.projectId);
  const nextStatus = statuses[Math.min(statuses.findIndex((item) => item.id === task.status) + 1, statuses.length - 1)];
  card.className = "task-card";
  card.draggable = false;
  card.dataset.taskId = task.id;
  card.addEventListener("pointerdown", (event) => {
    startDrag(event, card, task.id, "pointer");
  });
  card.addEventListener("mousedown", (event) => startDrag(event, card, task.id, "mouse"));
  card.innerHTML = `<h3>${escapeHtml(task.title)}</h3>${task.description ? `<p>${escapeHtml(task.description)}</p>` : ""}<div class="task-meta"><span>${project ? escapeHtml(project.title) : "No project"}</span><span>${task.status === "done" ? "Complete" : ""}</span></div><div class="task-actions">${task.status !== "done" ? `<button type="button" data-next="${task.id}">Move to ${nextStatus.label}</button>` : ""}<button type="button" data-delete="${task.id}" aria-label="Delete ${escapeHtml(task.title)}">Delete</button></div>`;
  card.querySelector("[data-next]")?.addEventListener("click", async () => {
    await runAction(async () => {
      await moveTask(task.id, nextStatus.id);
    });
  });
  card.querySelector("[data-delete]").addEventListener("click", async () => {
    await runAction(async () => {
      await apiRequest(`/api/tasks/${task.id}`, { method: "DELETE" });
      await loadState();
    });
  });
  return card;
}

function startDrag(event, card, taskId, type) {
  if (event.button !== 0 || event.target.closest("button")) return;
  if (pointerDrag || mouseDrag) return;
  const bounds = card.getBoundingClientRect();
  const drag = {
    card,
    taskId,
    target: null,
    offsetX: event.clientX - bounds.left,
    offsetY: event.clientY - bounds.top,
    preview: card.cloneNode(true)
  };
  drag.preview.classList.add("drag-preview");
  drag.preview.removeAttribute("data-task-id");
  drag.preview.style.width = `${bounds.width}px`;
  document.body.append(drag.preview);
  moveDragPreview(drag, event.clientX, event.clientY);
  if (type === "pointer") {
    drag.pointerId = event.pointerId;
    pointerDrag = drag;
  } else {
    mouseDrag = drag;
  }
  card.classList.add("dragging");
  event.preventDefault();
}

document.addEventListener("pointermove", (event) => {
  if (!pointerDrag || pointerDrag.pointerId !== event.pointerId) return;
  moveDragPreview(pointerDrag, event.clientX, event.clientY);
  const target = document.elementFromPoint(event.clientX, event.clientY)?.closest(".column, .project-task-group");
  if (pointerDrag.target && pointerDrag.target !== target) pointerDrag.target.classList.remove("drop-target");
  pointerDrag.target = target;
  target?.classList.add("drop-target");
});

document.addEventListener("pointerup", async (event) => {
  if (!pointerDrag || pointerDrag.pointerId !== event.pointerId) return;
  const drag = pointerDrag;
  const dropZone = [...document.querySelectorAll(".column, .project-task-group")]
    .find((element) => {
      const bounds = element.getBoundingClientRect();
      return event.clientX >= bounds.left && event.clientX <= bounds.right
        && event.clientY >= bounds.top && event.clientY <= bounds.bottom;
    });
  const status = dropZone?.dataset.status || projectGroupStatus(dropZone?.dataset.group);
  drag.card.classList.remove("dragging");
  drag.preview.remove();
  drag.target?.classList.remove("drop-target");
  dropZone?.classList.remove("drop-target");
  pointerDrag = null;
  if (status) await moveTask(drag.taskId, status);
});

document.addEventListener("pointercancel", () => {
  pointerDrag?.target?.classList.remove("drop-target");
  pointerDrag?.card.classList.remove("dragging");
  pointerDrag?.preview.remove();
  pointerDrag = null;
});

document.addEventListener("mousemove", (event) => {
  if (!mouseDrag) return;
  moveDragPreview(mouseDrag, event.clientX, event.clientY);
  updateDragTarget(mouseDrag, event.clientX, event.clientY);
});

document.addEventListener("mouseup", async (event) => {
  if (!mouseDrag) return;
  const drag = mouseDrag;
  const status = finishDrag(drag, event.clientX, event.clientY);
  mouseDrag = null;
  if (status) await moveTask(drag.taskId, status);
});

function updateDragTarget(drag, clientX, clientY) {
  const target = document.elementFromPoint(clientX, clientY)?.closest(".column, .project-task-group");
  if (drag.target && drag.target !== target) drag.target.classList.remove("drop-target");
  drag.target = target;
  target?.classList.add("drop-target");
}

function moveDragPreview(drag, clientX, clientY) {
  drag.preview.style.left = `${clientX - drag.offsetX}px`;
  drag.preview.style.top = `${clientY - drag.offsetY}px`;
}

function finishDrag(drag, clientX, clientY) {
  const dropZone = [...document.querySelectorAll(".column, .project-task-group")]
    .find((element) => {
      const bounds = element.getBoundingClientRect();
      return clientX >= bounds.left && clientX <= bounds.right
        && clientY >= bounds.top && clientY <= bounds.bottom;
    });
  const status = dropZone?.dataset.status || projectGroupStatus(dropZone?.dataset.group);
  drag.card.classList.remove("dragging");
  drag.preview.remove();
  drag.target?.classList.remove("drop-target");
  dropZone?.classList.remove("drop-target");
  return status;
}

function projectGroupStatus(group) {
  if (group === "new") return "new";
  if (group === "active") return "ready";
  if (group === "complete") return "done";
  return null;
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
    card.innerHTML = `<h3>${escapeHtml(project.title)}</h3><p>${escapeHtml(project.description || "A project without a description. Start with one small step.")}</p><div class="goal-progress"><span>${completed} of ${tasks.length} tasks complete</span><strong>${percent}%</strong></div><div class="progress-track"><span style="width:${percent}%"></span></div>`;
    card.addEventListener("click", () => openProject(project.id));
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openProject(project.id);
      }
    });
    grid.append(card);
  });
  if (!state.projects.length) grid.innerHTML = '<div class="empty-state"><span class="empty-icon">◎</span><h3>Start with a project</h3><p>A clear destination makes the next step easier to see.</p></div>';
}

function openProject(projectId) {
  detailProjectId = projectId;
  selectedProject = projectId;
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
  $("#project-summary").innerHTML = groups.map((group) => {
    const count = tasks.filter((task) => group.statuses.includes(task.status)).length;
    return `<div class="summary-card"><span>${group.label}</span><strong>${count}</strong></div>`;
  }).join("");
  const container = $("#project-task-groups");
  container.innerHTML = "";
  groups.forEach((group) => {
    const groupTasks = tasks.filter((task) => group.statuses.includes(task.status));
    const section = document.createElement("section");
    section.className = "project-task-group";
    section.innerHTML = `<div class="project-group-heading"><div><h3>${group.label}</h3><p>${group.description}</p></div><span class="count">${groupTasks.length}</span></div><div class="project-group-tasks"></div>`;
    const taskContainer = section.querySelector(".project-group-tasks");
    section.dataset.group = group.label.toLowerCase();
    section.addEventListener("dragover", (event) => {
      event.preventDefault();
      section.classList.add("drop-target");
    });
    section.addEventListener("dragleave", () => section.classList.remove("drop-target"));
    section.addEventListener("drop", async (event) => {
      event.preventDefault();
      section.classList.remove("drop-target");
      const taskId = event.dataTransfer.getData("text/plain");
      const targetStatus = group.label === "New" ? "new" : group.label === "Active" ? "ready" : "done";
      await moveTask(taskId, targetStatus);
    });
    if (!groupTasks.length) taskContainer.innerHTML = "<p class=\"project-empty\">No tasks in this group.</p>";
    groupTasks.forEach((task) => taskContainer.append(createTaskCard(task)));
    container.append(section);
  });
}

function showView(view) {
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

async function runAction(action) {
  try {
    await action();
  } catch (error) {
    showError(error);
  }
}

async function moveTask(taskId, status) {
  await runAction(async () => {
    await apiRequest(`/api/tasks/${taskId}`, { method: "PATCH", body: JSON.stringify({ status }) });
    await loadState();
  });
}

function showError(error) {
  window.alert(error.message);
}

function openTaskModal(projectId = null) {
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

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[character]));
}

$("#new-task-button").addEventListener("click", openTaskModal);
$("#new-goal-button").addEventListener("click", openGoalModal);
$("#goals-new-button").addEventListener("click", openGoalModal);
document.querySelectorAll("[data-close]").forEach((button) => button.addEventListener("click", () => $(`#${button.dataset.close}`).close()));
document.querySelectorAll(".nav-item").forEach((button) => button.addEventListener("click", () => {
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.remove("active"));
  button.classList.add("active");
  detailProjectId = null;
  showView(button.dataset.view);
}));
$("#back-to-projects").addEventListener("click", () => {
  detailProjectId = null;
  showView("goals");
});
$("#project-new-task-button").addEventListener("click", () => openTaskModal(detailProjectId));
$("#task-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  await runAction(async () => {
    await apiRequest("/api/tasks", {
      method: "POST",
      body: JSON.stringify({ title: form.get("title"), description: form.get("description"), projectId: form.get("project") })
    });
    event.currentTarget.closest("dialog").close();
    await loadState();
  });
});
$("#goal-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  await runAction(async () => {
    const project = await apiRequest("/api/projects", {
      method: "POST",
      body: JSON.stringify({ title: form.get("title"), description: form.get("description") })
    });
    selectedProject = project.id;
    event.currentTarget.closest("dialog").close();
    await loadState();
  });
});
document.addEventListener("click", (event) => {
  if (event.target.matches('[data-action="new-task"]')) openTaskModal();
});

loadState();
