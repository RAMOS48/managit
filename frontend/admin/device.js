const REFRESH_MS = 10000;
const HISTORY_ROWS = 20;
const deviceId = Number(new URLSearchParams(location.search).get("id"));

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
  badge.className = "badge " + status;
  badge.textContent = status;
  return badge;
}

function renderDevice(device) {
  document.title = "ManaGit - " + device.hostname;
  document.getElementById("title").textContent = device.hostname;
  document.getElementById("status-badge").replaceChildren(statusBadge(device.status));

  const info = document.getElementById("info");
  info.replaceChildren();
  addInfo(info, "Status", statusBadge(device.status));
  addInfo(info, "Type", device.device_type);
  addInfo(info, "Operating system", device.os);
  addInfo(info, "IP address", device.ip_address);
  addInfo(info, "Department", device.department);
  addInfo(info, "Owner", device.owner);
  addInfo(info, "Agent version", device.agent_version);
  addInfo(info, "Agent ID", device.agent_id);
  addInfo(info, "Simulated", device.is_simulated ? "Yes" : "No");
  addInfo(info, "Registered", parseUtc(device.created_at).toLocaleString());
  const lastSeen = device.last_seen
    ? timeAgo(device.last_seen) + " (" + parseUtc(device.last_seen).toLocaleString() + ")"
    : "never";
  addInfo(info, "Last seen", lastSeen);
}

function meterRow(label, value) {
  const row = document.createElement("div");
  row.className = "meter";

  const head = document.createElement("div");
  head.className = "meter-head";
  const name = document.createElement("span");
  name.textContent = label;
  const number = document.createElement("span");
  number.textContent = value.toFixed(0) + "%";
  head.appendChild(name);
  head.appendChild(number);

  const bar = document.createElement("div");
  bar.className = "bar";
  const fill = document.createElement("div");
  fill.className = "fill" + (value >= 85 ? " high" : "");
  fill.style.width = Math.min(100, Math.max(0, value)) + "%";
  bar.appendChild(fill);

  row.appendChild(head);
  row.appendChild(bar);
  return row;
}

function renderMeters(device) {
  const box = document.getElementById("meters");
  const time = document.getElementById("metrics-time");
  box.replaceChildren();
  const m = device.latest_metrics;
  if (!m) {
    box.textContent = "No metrics received yet.";
    time.textContent = "";
    return;
  }
  box.appendChild(meterRow("CPU", m.cpu_percent));
  box.appendChild(meterRow("RAM", m.memory_percent));
  box.appendChild(meterRow("Disk", m.disk_percent));
  time.textContent = "Collected " + timeAgo(m.collected_at);
}

function cell(text, className) {
  const td = document.createElement("td");
  td.textContent = text;
  if (className) td.className = className;
  return td;
}

function renderHistory(metrics) {
  const body = document.getElementById("history-rows");
  body.replaceChildren();
  if (metrics.length === 0) {
    const tr = document.createElement("tr");
    const td = cell("No metrics yet.");
    td.colSpan = 4;
    tr.appendChild(td);
    body.appendChild(tr);
    return;
  }
  for (const m of metrics) {
    const tr = document.createElement("tr");
    tr.appendChild(cell(parseUtc(m.collected_at).toLocaleTimeString()));
    tr.appendChild(cell(m.cpu_percent.toFixed(1) + "%", m.cpu_percent >= 85 ? "warn" : ""));
    tr.appendChild(cell(m.memory_percent.toFixed(1) + "%", m.memory_percent >= 85 ? "warn" : ""));
    tr.appendChild(cell(m.disk_percent.toFixed(1) + "%", m.disk_percent >= 85 ? "warn" : ""));
    body.appendChild(tr);
  }
}

async function load() {
  if (!Number.isInteger(deviceId) || deviceId < 1) {
    document.getElementById("title").textContent = "Invalid device";
    showError("The device id in the address is missing or invalid.");
    return false;
  }
  try {
    const [device, metrics] = await Promise.all([
      api("/api/devices/" + deviceId),
      api("/api/devices/" + deviceId + "/metrics?limit=" + HISTORY_ROWS),
    ]);
    renderDevice(device);
    renderMeters(device);
    renderHistory(metrics);
    showError("");
    return true;
  } catch (err) {
    if (err.message.startsWith("404")) {
      document.getElementById("title").textContent = "Device not found";
      showError("No device with id " + deviceId + ".");
      return false;
    }
    showError("Could not load data from the server: " + err.message);
    return true;
  }
}

async function start() {
  const keepGoing = await load();
  if (keepGoing) setInterval(load, REFRESH_MS);
}

start();
