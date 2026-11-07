// Shared helpers for all admin pages.
// Everything from the API is inserted with textContent, never innerHTML,
// so a malicious hostname sent by an agent cannot inject HTML or scripts.

async function api(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(response.status + " " + response.statusText);
  }
  return response.json();
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
