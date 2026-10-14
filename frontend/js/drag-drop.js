import { moveTask } from "./api.js";

let pointerDrag = null;
let mouseDrag = null;

export function initializeDragDrop(dropZone, status) {
  dropZone.addEventListener("dragover", (event) => { event.preventDefault(); dropZone.classList.add("drop-target"); });
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drop-target"));
  dropZone.addEventListener("drop", async (event) => {
    event.preventDefault();
    dropZone.classList.remove("drop-target");
    const taskId = event.dataTransfer.getData("text/plain");
    await moveTask(taskId, status);
  });
}

export function startDrag(event, card, taskId, type) {
  if (event.button !== 0 || event.target.closest("button") || pointerDrag || mouseDrag) return;
  const bounds = card.getBoundingClientRect();
  const drag = { card, taskId, target: null, offsetX: event.clientX - bounds.left, offsetY: event.clientY - bounds.top, preview: card.cloneNode(true) };
  drag.preview.classList.add("drag-preview");
  drag.preview.removeAttribute("data-task-id");
  drag.preview.style.width = `${bounds.width}px`;
  document.body.append(drag.preview);
  moveDragPreview(drag, event.clientX, event.clientY);
  if (type === "pointer") { drag.pointerId = event.pointerId; pointerDrag = drag; } else mouseDrag = drag;
  card.classList.add("dragging");
  event.preventDefault();
}

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
  const dropZone = [...document.querySelectorAll(".column, .project-task-group")].find((element) => {
    const bounds = element.getBoundingClientRect();
    return clientX >= bounds.left && clientX <= bounds.right && clientY >= bounds.top && clientY <= bounds.bottom;
  });
  const status = dropZone?.dataset.status || ({ new: "new", active: "ready", complete: "done" }[dropZone?.dataset.group]);
  drag.card.classList.remove("dragging");
  drag.preview.remove();
  drag.target?.classList.remove("drop-target");
  dropZone?.classList.remove("drop-target");
  return status;
}

document.addEventListener("pointermove", (event) => {
  if (pointerDrag?.pointerId === event.pointerId) {
    moveDragPreview(pointerDrag, event.clientX, event.clientY);
    updateDragTarget(pointerDrag, event.clientX, event.clientY);
  }
});
document.addEventListener("pointerup", async (event) => {
  if (pointerDrag?.pointerId !== event.pointerId) return;
  const drag = pointerDrag;
  const status = finishDrag(drag, event.clientX, event.clientY);
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
  if (mouseDrag) { moveDragPreview(mouseDrag, event.clientX, event.clientY); updateDragTarget(mouseDrag, event.clientX, event.clientY); }
});
document.addEventListener("mouseup", async (event) => {
  if (!mouseDrag) return;
  const drag = mouseDrag;
  const status = finishDrag(drag, event.clientX, event.clientY);
  mouseDrag = null;
  if (status) await moveTask(drag.taskId, status);
});
