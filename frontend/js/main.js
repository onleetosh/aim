import { loadState } from "./api.js";
import { setDetailProjectId } from "./config.js";
import { showView } from "./render.js";
import { initializeModals } from "./modals.js";

document.querySelectorAll(".nav-item").forEach((button) => button.addEventListener("click", () => {
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.remove("active"));
  button.classList.add("active");
  setDetailProjectId(null);
  showView(button.dataset.view);
}));
document.querySelector("#back-to-projects").addEventListener("click", () => {
  setDetailProjectId(null);
  showView("goals");
});

initializeModals();
loadState();
