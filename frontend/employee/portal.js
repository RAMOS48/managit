// Employee portal. Server data is inserted with textContent only.
const el = (id) => document.getElementById(id);

function goToLogin() {
  location.href = "/login/";
}

async function getJson(path) {
  const response = await fetch(path);
  if (response.status === 401) {
    goToLogin();
    throw new Error("Session expired");
  }
  if (!response.ok) throw new Error(response.status + " " + response.statusText);
  return response.json();
}

async function postJson(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  let data = null;
  try {
    data = await response.json();
  } catch (err) {
    // no JSON body
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

function showError(text) {
  const box = el("error");
  box.textContent = text;
  box.hidden = !text;
}

function showSuccess(reference) {
  const box = el("success");
  box.replaceChildren();
  box.append("Your ticket was submitted. Reference: ");
  const strong = document.createElement("strong");
  strong.textContent = reference;
  box.appendChild(strong);
  box.append(". Please keep it if you need to follow up.");
  box.hidden = false;
}

function fillSelect(select, items, valueOf, labelOf) {
  select.replaceChildren();
  for (const item of items) {
    const option = document.createElement("option");
    option.value = valueOf(item);
    option.textContent = labelOf(item);
    select.appendChild(option);
  }
}

function parseUtc(value) {
  const hasZone = /Z$|[+-]\d\d:\d\d$/.test(value);
  return new Date(hasZone ? value : value + "Z");
}

function buildUserBox(me) {
  const header = document.querySelector("header");
  const box = document.createElement("div");
  box.className = "userbox";

  if (me.role === "admin") {
    const link = document.createElement("a");
    link.href = "/admin/";
    link.textContent = "Admin dashboard";
    box.appendChild(link);
  }

  const name = document.createElement("span");
  name.textContent = me.full_name || me.username;
  box.appendChild(name);

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
  box.appendChild(button);
  header.appendChild(box);
}

function cell(text) {
  const td = document.createElement("td");
  td.textContent = text || "-";
  return td;
}

function renderTickets(tickets) {
  const body = el("my-rows");
  body.replaceChildren();

  if (tickets.length === 0) {
    const tr = document.createElement("tr");
    const td = cell("You have not submitted any ticket yet.");
    td.colSpan = 5;
    tr.appendChild(td);
    body.appendChild(tr);
    return;
  }

  for (const ticket of tickets) {
    const tr = document.createElement("tr");
    tr.appendChild(cell(ticket.reference));
    tr.appendChild(cell(ticket.title));

    const statusTd = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = "badge " + ticket.status.toLowerCase().replace(/ /g, "-");
    badge.textContent = ticket.status;
    statusTd.appendChild(badge);
    tr.appendChild(statusTd);

    tr.appendChild(cell(parseUtc(ticket.created_at).toLocaleString()));
    tr.appendChild(cell(ticket.resolution_note));
    body.appendChild(tr);
  }
}

async function loadTickets() {
  try {
    renderTickets(await getJson("/api/my/tickets?limit=20"));
  } catch (err) {
    // a real problem is already shown by the form code
  }
}

async function init() {
  let me;
  try {
    me = await getJson("/api/auth/me");
  } catch (err) {
    return; // not logged in: already redirected to the login page
  }
  buildUserBox(me);

  try {
    const [options, devices] = await Promise.all([
      getJson("/api/portal/options"),
      getJson("/api/portal/devices"),
    ]);
    fillSelect(el("f-category"), options.categories, (c) => c, (c) => c);
    fillSelect(el("f-priority"), options.priorities, (p) => p, (p) => p);
    el("f-priority").value = "Medium";

    const choices = [{ id: "", hostname: "Not about a specific device" }, ...devices];
    fillSelect(el("f-device"), choices, (d) => d.id, (d) => d.hostname);
  } catch (err) {
    showError("Could not load the form data: " + err.message);
    el("f-submit").disabled = true;
  }
  loadTickets();
}

el("ticket-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  showError("");
  el("success").hidden = true;

  const deviceValue = el("f-device").value;
  const body = {
    device_id: deviceValue === "" ? null : Number(deviceValue),
    category: el("f-category").value,
    priority: el("f-priority").value,
    title: el("f-title").value.trim(),
    description: el("f-description").value.trim(),
  };

  const button = el("f-submit");
  button.disabled = true;
  try {
    const ticket = await postJson("/api/tickets", body);
    showSuccess(ticket.reference);
    el("f-title").value = "";
    el("f-description").value = "";
    el("f-device").value = "";
    el("f-priority").value = "Medium";
    window.scrollTo(0, 0);
    loadTickets();
  } catch (err) {
    showError(err.message);
  } finally {
    button.disabled = false;
  }
});

init();
