// Keep transport details out of rendering and form modules.
import { state } from "./config.js";
import { render } from "./render.js";
import { localDate, showError } from "./utils.js";

const LOCAL_STORAGE_KEY = "aim-file-mode-state";
// Opening index.html directly uses localStorage because fetch cannot reach Flask.
const fileMode = window.location.protocol === "file:";

export async function apiRequest(path, options = {}) {
  if (fileMode) return localRequest(path, options);
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options
  });
  if (response.status === 401) {
    // The session expired; reloading shows the login screen.
    window.location.reload();
    throw new Error("Your session has expired. Please log in again.");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error || "The server could not complete that request.");
  }
  return response.status === 204 ? null : response.json();
}

function localRequest(path, options = {}) {
  // Mirror the API endpoints closely so file mode remains useful for demos.
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
  if (projectMatch && options.method === "DELETE") {
    const projectExists = localState.projects.some((project) => project.id === projectMatch[1]);
    if (!projectExists) throw new Error("Project not found.");
    localState.projects = localState.projects.filter((project) => project.id !== projectMatch[1]);
    localState.tasks = localState.tasks.filter((task) => task.projectId !== projectMatch[1]);
    saveLocalState(localState);
    return null;
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
    if (body.status !== undefined) task.status = body.status;
    if (body.title !== undefined) task.title = String(body.title).trim();
    if (body.description !== undefined) task.description = String(body.description).trim();
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

export async function loadState() {
  try {
    const nextState = await apiRequest("/api/state");
    state.projects = nextState.projects;
    state.tasks = nextState.tasks;
    render();
  } catch (error) {
    showError(error);
  }
}

export async function moveTask(taskId, status) {
  const { runAction } = await import("./utils.js");
  await runAction(async () => {
    await apiRequest(`/api/tasks/${taskId}`, {
      method: "PATCH",
      body: JSON.stringify({ status, today: localDate() })
    });
    await loadState();
  });
}
