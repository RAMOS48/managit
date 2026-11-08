const el = (id) => document.getElementById(id);

function showError(text) {
  const box = el("error");
  box.textContent = text;
  box.hidden = !text;
}

function goHome(role) {
  location.href = role === "admin" ? "/admin/" : "/portal/";
}

// Already logged in? Skip the form.
async function checkExisting() {
  try {
    const response = await fetch("/api/auth/me");
    if (response.ok) {
      const me = await response.json();
      goHome(me.role);
    }
  } catch (err) {
    // not logged in, or the server is unreachable: show the form
  }
}

el("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  showError("");
  const button = el("l-submit");
  button.disabled = true;
  try {
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: el("l-username").value.trim(),
        password: el("l-password").value,
      }),
    });
    let data = null;
    try {
      data = await response.json();
    } catch (err) {
      // no JSON body
    }
    if (!response.ok) {
      let detail = response.status + " " + response.statusText;
      if (data && typeof data.detail === "string") {
        detail = data.detail;
      } else if (data && Array.isArray(data.detail)) {
        detail = data.detail.map((d) => d.msg).join("; ");
      }
      showError(detail);
      el("l-password").value = "";
      return;
    }
    goHome(data.role);
  } catch (err) {
    showError("Could not reach the server.");
  } finally {
    button.disabled = false;
  }
});

checkExisting();
