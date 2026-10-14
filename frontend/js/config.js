// Shared UI state is kept in one module so renderers and event handlers agree.
export const statuses = [
  { id: "new", label: "New" },
  { id: "ready", label: "Ready" },
  { id: "progress", label: "In progress" },
  { id: "review", label: "Review" },
  { id: "done", label: "Done" }
];

export const state = { projects: [], tasks: [] };
export let selectedProject = "all";
export let detailProjectId = null;

export function setSelectedProject(projectId) {
  selectedProject = projectId;
}

export function setDetailProjectId(projectId) {
  detailProjectId = projectId;
}
