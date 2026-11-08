// Employee portal. Server data is inserted with textContent only.
const el = (id) => document.getElementById(id);

async function getJson(path) {
  const response = await fetch(path);
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

async function init() {
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
}

el("ticket-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  showError("");
  el("success").hidden = true;

  const deviceValue = el("f-device").value;
  const body = {
    requester_name: el("f-name").value.trim(),
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
  } catch (err) {
    showError(err.message);
  } finally {
    button.disabled = false;
  }
});

init();
