const REFRESH_MS = 15000;
let tickets = [];

function cell(text) {
  const td = document.createElement("td");
  td.textContent = text || "-";
  return td;
}

function statusClass(status) {
  return status.toLowerCase().replace(/ /g, "-");
}

function matches(ticket) {
  const status = document.getElementById("status-filter").value;
  const priority = document.getElementById("priority-filter").value;
  const query = document.getElementById("search").value.trim().toLowerCase();

  if (status === "active" && ticket.status === "Resolved") return false;
  if (status !== "active" && status !== "all" && ticket.status !== status) return false;
  if (priority !== "all" && ticket.priority !== priority) return false;
  if (!query) return true;
  return [ticket.reference, ticket.title, ticket.requester_name, ticket.device_hostname, ticket.category]
    .some((field) => (field || "").toLowerCase().includes(query));
}

function render() {
  const body = document.getElementById("ticket-rows");
  body.replaceChildren();
  const rows = tickets.filter(matches);

  if (rows.length === 0) {
    const tr = document.createElement("tr");
    const td = cell("No tickets match.");
    td.colSpan = 8;
    tr.appendChild(td);
    body.appendChild(tr);
    return;
  }

  for (const ticket of rows) {
    const tr = document.createElement("tr");

    const refTd = document.createElement("td");
    const link = document.createElement("a");
    link.href = "ticket.html?id=" + encodeURIComponent(ticket.id);
    link.textContent = ticket.reference;
    refTd.appendChild(link);
    tr.appendChild(refTd);

    const prioTd = document.createElement("td");
    const prio = document.createElement("span");
    prio.className = "prio " + ticket.priority.toLowerCase();
    prio.textContent = ticket.priority;
    prioTd.appendChild(prio);
    tr.appendChild(prioTd);

    tr.appendChild(cell(ticket.title));
    tr.appendChild(cell(ticket.category));
    tr.appendChild(cell(ticket.device_hostname));
    tr.appendChild(cell(ticket.requester_name));

    const statusTd = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = "badge " + statusClass(ticket.status);
    badge.textContent = ticket.status;
    statusTd.appendChild(badge);
    tr.appendChild(statusTd);

    tr.appendChild(cell(timeAgo(ticket.created_at)));
    body.appendChild(tr);
  }
}

async function load() {
  try {
    tickets = await api("/api/tickets?limit=500");
    render();
    document.getElementById("refreshed").textContent =
      "Updated " + new Date().toLocaleTimeString();
    showError("");
  } catch (err) {
    showError("Could not load tickets: " + err.message);
  }
}

document.getElementById("search").addEventListener("input", render);
document.getElementById("status-filter").addEventListener("change", render);
document.getElementById("priority-filter").addEventListener("change", render);

load();
setInterval(load, REFRESH_MS);
