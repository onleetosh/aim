// Small browser helpers shared by the UI modules.
export const $ = (selector) => document.querySelector(selector);

export function escapeHtml(value) {
  return String(value).replace(
    /[&<>"']/g,
    (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[character])
  );
}

export function showError(error) {
  window.alert(error.message);
}

export async function runAction(action) {
  try {
    await action();
  } catch (error) {
    showError(error);
  }
}
