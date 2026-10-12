const statuses = [
  { id: "ready", label: "Ready" },
  { id: "progress", label: "In progress" },
  { id: "review", label: "Review" },
  { id: "done", label: "Done" }
];

let state = { projects: [], tasks: [] };
let selectedProject = "all";

const $ = (selector) => document.querySelector(selector);

async function apiRequest(path, options = {}) {
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
    const column = document.createElement("section");
    column.className = "column";
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
  card.innerHTML = `<h3>${escapeHtml(task.title)}</h3>${task.description ? `<p>${escapeHtml(task.description)}</p>` : ""}<div class="task-meta"><span>${project ? escapeHtml(project.title) : "No project"}</span><span>${task.status === "done" ? "Complete" : ""}</span></div><div class="task-actions">${task.status !== "done" ? `<button type="button" data-next="${task.id}">Move to ${nextStatus.label}</button>` : ""}<button type="button" data-delete="${task.id}" aria-label="Delete ${escapeHtml(task.title)}">Delete</button></div>`;
  card.querySelector("[data-next]")?.addEventListener("click", async () => {
    await runAction(async () => {
      await apiRequest(`/api/tasks/${task.id}`, { method: "PATCH", body: JSON.stringify({ status: nextStatus.id }) });
      await loadState();
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

function renderProjects() {
  const grid = $("#goals-grid");
  grid.innerHTML = "";
  state.projects.forEach((project) => {
    const tasks = state.tasks.filter((task) => task.projectId === project.id);
    const completed = tasks.filter((task) => task.status === "done").length;
    const percent = tasks.length ? Math.round((completed / tasks.length) * 100) : 0;
    const card = document.createElement("article");
    card.className = "goal-card";
    card.innerHTML = `<h3>${escapeHtml(project.title)}</h3><p>${escapeHtml(project.description || "A project without a description. Start with one small step.")}</p><div class="goal-progress"><span>${completed} of ${tasks.length} tasks complete</span><strong>${percent}%</strong></div><div class="progress-track"><span style="width:${percent}%"></span></div>`;
    grid.append(card);
  });
  if (!state.projects.length) grid.innerHTML = '<div class="empty-state"><span class="empty-icon">◎</span><h3>Start with a project</h3><p>A clear destination makes the next step easier to see.</p></div>';
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

function showError(error) {
  window.alert(error.message);
}

function openTaskModal() {
  $("#task-form").reset();
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
  $("#board-view").classList.toggle("hidden", button.dataset.view !== "board");
  $("#goals-view").classList.toggle("hidden", button.dataset.view !== "goals");
}));
$("#task-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  await runAction(async () => {
    await apiRequest("/api/tasks", {
      method: "POST",
      body: JSON.stringify({ title: form.get("title"), description: form.get("description"), projectId: form.get("goal") })
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
