// Shared helpers for all admin pages.
// Everything from the API is inserted with textContent, never innerHTML,
// so a malicious hostname sent by an agent cannot inject HTML or scripts.

function goToLogin() {
  location.href = "/login/";
}

async function api(path) {
  const response = await fetch(path);
  if (response.status === 401) {
    goToLogin();
    throw new Error("Session expired");
  }
  if (!response.ok) {
    throw new Error(response.status + " " + response.statusText);
  }
  return response.json();
}

async function sendJson(method, path, body) {
  const response = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  let data = null;
  try {
    data = await response.json();
  } catch (err) {
    // the response had no JSON body
  }
  if (response.status === 401) {
    goToLogin();
    throw new Error("Session expired");
  }
  if (!response.ok) {
    let detail = response.status + " " + response.statusText;
    if (data && typeof data.detail === "string") {
      detail = data.detail;
    } else if (data && Array.isArray(data.detail)) {
      detail = data.detail.map((d) => d.msg).join("; ");
    }
    throw new Error(detail);
  }
  return data;
}

function apiPost(path, body) {
  return sendJson("POST", path, body);
}

function apiPatch(path, body) {
  return sendJson("PATCH", path, body);
}

// The server sends naive UTC timestamps (no timezone), so mark them as UTC.
function parseUtc(value) {
  if (!value) return null;
  const hasZone = /Z$|[+-]\d\d:\d\d$/.test(value);
  return new Date(hasZone ? value : value + "Z");
}

function timeAgo(value) {
  const date = parseUtc(value);
  if (!date) return "never";
  const seconds = Math.max(0, Math.round((Date.now() - date.getTime()) / 1000));
  if (seconds < 60) return seconds + " s ago";
  if (seconds < 3600) return Math.floor(seconds / 60) + " min ago";
  if (seconds < 86400) return Math.floor(seconds / 3600) + " h ago";
  return Math.floor(seconds / 86400) + " d ago";
}

function showError(message) {
  const box = document.getElementById("error");
  if (!box) return;
  box.textContent = message;
  box.hidden = !message;
}

// Session guard: login required, administrators only, plus the user box in the header.
async function initSession() {
  let me;
  try {
    const response = await fetch("/api/auth/me");
    if (response.status === 401) {
      goToLogin();
      return;
    }
    if (!response.ok) return;
    me = await response.json();
  } catch (err) {
    return;
  }

  if (me.role !== "admin") {
    location.href = "/portal/";
    return;
  }

  const header = document.querySelector("header");
  if (!header) return;
  const box = document.createElement("div");
  box.className = "userbox";

  const name = document.createElement("span");
  name.textContent = me.full_name || me.username;

  const button = document.createElement("button");
  button.type = "button";
  button.className = "logout";
  button.textContent = "Log out";
  button.addEventListener("click", async () => {
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } catch (err) {
      // leave anyway
    }
    goToLogin();
  });

  box.appendChild(name);
  box.appendChild(button);
  header.appendChild(box);
}

initSession();
