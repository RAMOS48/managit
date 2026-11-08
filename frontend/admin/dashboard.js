const REFRESH_MS = 10000;
let devices = [];

function textCell(text) {
  const td = document.createElement("td");
  td.textContent = text || "-";
  return td;
}

function metricCell(metrics, key) {
  const td = document.createElement("td");
  if (!metrics) {
    td.textContent = "-";
    return td;
  }
  const value = metrics[key];
  td.textContent = value.toFixed(0) + "%";
  if (value >= 85) td.className = "warn";
  return td;
}

function statusCell(status) {
  const td = document.createElement("td");
  const badge = document.createElement("span");
  badge.className = "badge " + status;
  badge.textContent = status;
  td.appendChild(badge);
  return td;
}

function hostnameCell(device) {
  const td = document.createElement("td");
  const link = document.createElement("a");
  link.href = "device.html?id=" + encodeURIComponent(device.id);
  link.textContent = device.hostname;
  td.appendChild(link);
  if (device.is_simulated) {
    const tag = document.createElement("span");
    tag.className = "tag";
    tag.textContent = "simulated";
    td.appendChild(tag);
  }
  return td;
}

function matchesFilters(device) {
  const query = document.getElementById("search").value.trim().toLowerCase();
  const status = document.getElementById("status-filter").value;
  if (status !== "all" && device.status !== status) return false;
  if (!query) return true;
  return [device.hostname, device.ip_address, device.department, device.owner, device.os]
    .some((field) => (field || "").toLowerCase().includes(query));
}

function renderTable() {
  const body = document.getElementById("device-rows");
  body.replaceChildren();

  const rows = devices.filter(matchesFilters).sort((a, b) => {
    if (a.status !== b.status) return a.status === "online" ? -1 : 1;
    return a.hostname.localeCompare(b.hostname);
  });

  if (rows.length === 0) {
    const tr = document.createElement("tr");
    const td = textCell("No devices match.");
    td.colSpan = 11;
    tr.appendChild(td);
    body.appendChild(tr);
    return;
  }

  for (const device of rows) {
    const tr = document.createElement("tr");
    tr.appendChild(statusCell(device.status));
    tr.appendChild(hostnameCell(device));
    tr.appendChild(textCell(device.device_type));
    tr.appendChild(textCell(device.os));
    tr.appendChild(textCell(device.ip_address));
    tr.appendChild(textCell(device.department));
    tr.appendChild(textCell(device.owner));
    tr.appendChild(metricCell(device.latest_metrics, "cpu_percent"));
    tr.appendChild(metricCell(device.latest_metrics, "memory_percent"));
    tr.appendChild(metricCell(device.latest_metrics, "disk_percent"));
    tr.appendChild(textCell(timeAgo(device.last_seen)));
    body.appendChild(tr);
  }
}

function renderCards(summary) {
  document.getElementById("c-total").textContent = summary.total;
  document.getElementById("c-online").textContent = summary.online;
  document.getElementById("c-offline").textContent = summary.offline;
  document.getElementById("c-simulated").textContent = summary.simulated;
  document.getElementById("c-tickets").textContent = summary.open_tickets;
  document.getElementById("c-progress").textContent = summary.in_progress_tickets;
}

async function load() {
  try {
    const [summary, deviceList] = await Promise.all([
      api("/api/monitoring/summary"),
      api("/api/devices"),
    ]);
    devices = deviceList;
    renderCards(summary);
    renderTable();
    document.getElementById("refreshed").textContent =
      "Updated " + new Date().toLocaleTimeString();
    showError("");
  } catch (err) {
    showError("Could not load data from the server: " + err.message);
  }
}

document.getElementById("search").addEventListener("input", renderTable);
document.getElementById("status-filter").addEventListener("change", renderTable);

load();
setInterval(load, REFRESH_MS);
