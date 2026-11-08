function recentCell(text) {
  const td = document.createElement("td");
  td.textContent = text || "-";
  return td;
}

function renderRecent(tickets) {
  const body = document.getElementById("recent-rows");
  body.replaceChildren();

  if (tickets.length === 0) {
    const tr = document.createElement("tr");
    const td = recentCell("No tickets yet.");
    td.colSpan = 6;
    tr.appendChild(td);
    body.appendChild(tr);
    return;
  }

  for (const ticket of tickets) {
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

    tr.appendChild(recentCell(ticket.title));
    tr.appendChild(recentCell(ticket.device_hostname));

    const statusTd = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = "badge " + ticket.status.toLowerCase().replace(/ /g, "-");
    badge.textContent = ticket.status;
    statusTd.appendChild(badge);
    tr.appendChild(statusTd);

    tr.appendChild(recentCell(timeAgo(ticket.created_at)));
    body.appendChild(tr);
  }
}

async function loadRecent() {
  try {
    renderRecent(await api("/api/tickets?limit=5"));
  } catch (err) {
    // the main dashboard code already shows connection errors
  }
}

loadRecent();
setInterval(loadRecent, 15000);
