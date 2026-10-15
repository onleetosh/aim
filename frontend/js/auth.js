// Login / sign-up screen shown to visitors without a session.
const form = document.querySelector("#auth-form");
const errorBox = document.querySelector("#auth-error");
const submitButton = document.querySelector("#auth-submit");
const switchButton = document.querySelector("#auth-switch-button");
let mode = "login";

const copy = {
  login: { eyebrow: "Welcome back", heading: "Log in", submit: "Log in", prompt: "New to A.I.M.?", switchLabel: "Create an account", autocomplete: "current-password" },
  register: { eyebrow: "Get started", heading: "Create your account", submit: "Sign up", prompt: "Already have an account?", switchLabel: "Log in", autocomplete: "new-password" }
};

function setMode(nextMode) {
  mode = nextMode;
  const text = copy[mode];
  document.querySelector("#auth-eyebrow").textContent = text.eyebrow;
  document.querySelector("#auth-heading").textContent = text.heading;
  submitButton.textContent = text.submit;
  document.querySelector("#auth-switch-text").textContent = text.prompt;
  switchButton.textContent = text.switchLabel;
  document.querySelector("#auth-password").autocomplete = text.autocomplete;
  document.querySelector("#auth-hint").classList.toggle("hidden", mode !== "register");
  showError("");
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.toggle("hidden", !message);
}

switchButton.addEventListener("click", () => setMode(mode === "login" ? "register" : "login"));

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = new FormData(form);
  submitButton.disabled = true;
  showError("");
  try {
    const response = await fetch(`/api/auth/${mode}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: data.get("username"), password: data.get("password") })
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.error || "Something went wrong. Please try again.");
    }
    window.location.reload();
  } catch (error) {
    showError(error.message);
    submitButton.disabled = false;
  }
});
