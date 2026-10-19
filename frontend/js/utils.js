// Small browser helpers shared by the UI modules.
export const $ = (selector) => document.querySelector(selector);

export function escapeHtml(value) {
  return String(value).replace(
    /[&<>"']/g,
    (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[character])
  );
}

// The browser's local calendar date as YYYY-MM-DD, so "today" matches the user's day.
export function localDate(now = new Date()) {
  const pad = (value) => String(value).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
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
