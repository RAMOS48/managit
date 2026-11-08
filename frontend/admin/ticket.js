const ticketId = Number(new URLSearchParams(location.search).get("id"));
const el = (id) => document.getElementById(id);

function addInfo(list, label, value) {
  const dt = document.createElement("dt");
  dt.textContent = label;
  const dd = document.createElement("dd");
  if (value instanceof Node) {
    dd.appendChild(value);
  } else {
    dd.textContent = value || "-";
  }
  list.appendChild(dt);
  list.appendChild(dd);
}

function statusBadge(status) {
  const badge = document.createElement("span");
  badge.className = "badge " + status.toLowerCase().replace(/ /g, "-");
  badge.textContent = status;
  return badge;
}

function prioritySpan(priority) {
  const span = document.createElement("span");
  span.className = "prio " + priority.toLowerCase();
  span.textContent = priority;
  return span;
}

function setMessage(text, isError) {
  const box = el("e-message");
  box.textContent = text;
  box.className = isError ? "msg-err" : "msg-ok";
}

function render(ticket, devices) {
  document.title = "ManaGit - " + ticket.reference;
  el("title").textContent = ticket.reference + " - " + ticket.title;
  el("status-badge").replaceChildren(statusBadge(ticket.status));

  const info = el("info");
  info.replaceChildren();
  addInfo(info, "Requester", ticket.requester_name);
  addInfo(info, "Category", ticket.category);
  addInfo(info, "Priority", prioritySpan(ticket.priority));
  if (ticket.device_id) {
    const link = document.createElement("a");
    link.href = "device.html?id=" + encodeURIComponent(ticket.device_id);
    link.textContent = ticket.device_hostname || ("Device " + ticket.device_id);
    addInfo(info, "Device", link);
  } else {
    addInfo(info, "Device", "Not linked to a device");
  }
  addInfo(info, "Created", parseUtc(ticket.created_at).toLocaleString());
  addInfo(info, "Last updated", parseUtc(ticket.updated_at).toLocaleString());

  el("desc").textContent = ticket.description;

  // Management form
  const deviceSelect = el("e-device");
  deviceSelect.replaceChildren();
  const none = document.createElement("option");
  none.value = "";
  none.textContent = "No device";
  deviceSelect.appendChild(none);
  for (const device of devices) {
    const option = document.createElement("option");
    option.value = String(device.id);
    option.textContent = device.hostname;
    deviceSelect.appendChild(option);
  }
  deviceSelect.value = ticket.device_id === null ? "" : String(ticket.device_id);
  el("e-status").value = ticket.status;
  el("e-note").value = ticket.resolution_note || "";
}

async function loadOptions() {
  const options = await api("/api/ticket-options");
  const select = el("e-status");
  select.replaceChildren();
  for (const status of options.statuses) {
    const option = document.createElement("option");
    option.value = status;
    option.textContent = status;
    select.appendChild(option);
  }
}

async function load() {
  try {
    const [ticket, devices] = await Promise.all([
      api("/api/tickets/" + ticketId),
      api("/api/portal/devices"),
    ]);
    render(ticket, devices);
    showError("");
  } catch (err) {
    if (err.message.startsWith("404")) {
      el("title").textContent = "Ticket not found";
      el("details").hidden = true;
      el("manage").hidden = true;
      showError("No ticket with id " + ticketId + ".");
      return;
    }
    showError("Could not load the ticket: " + err.message);
  }
}

el("edit-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  setMessage("", false);
  const deviceValue = el("e-device").value;
  const body = {
    status: el("e-status").value,
    device_id: deviceValue === "" ? null : Number(deviceValue),
    resolution_note: el("e-note").value.trim(),
  };
  const button = el("e-save");
  button.disabled = true;
  try {
    await apiPatch("/api/tickets/" + ticketId, body);
    setMessage("Saved.", false);
    await load();
  } catch (err) {
    setMessage(err.message, true);
  } finally {
    button.disabled = false;
  }
});

async function start() {
  if (!Number.isInteger(ticketId) || ticketId < 1) {
    el("title").textContent = "Invalid ticket";
    el("details").hidden = true;
    el("manage").hidden = true;
    showError("The ticket id in the address is missing or invalid.");
    return;
  }
  try {
    await loadOptions();
  } catch (err) {
    showError("Could not load the options: " + err.message);
    return;
  }
  load();
}

start();
