// Diagnostics panel for the device page. Uses deviceId from device.js.
// All server data is shown with textContent (never innerHTML).

let diagOps = {};
let diagJobs = [];
let diagSelectedId = null;
let diagWaitingFor = null;
let diagTimer = null;

const diagEl = (id) => document.getElementById(id);

function diagMessage(text, isError) {
  const box = diagEl("diag-message");
  box.textContent = text;
  box.className = isError ? "msg-err" : "msg-ok";
}

function diagOpLabel(name) {
  return diagOps[name] ? diagOps[name].label : name;
}

function diagParams(params) {
  const parts = Object.entries(params || {}).map(([key, value]) => key + "=" + value);
  return parts.length ? parts.join(" ") : "-";
}

function diagCell(text, className) {
  const td = document.createElement("td");
  td.textContent = text;
  if (className) td.className = className;
  return td;
}

function diagUpdateFields() {
  const spec = diagOps[diagEl("diag-op").value];
  const params = spec ? spec.params : [];
  diagEl("diag-host-wrap").hidden = !params.includes("host");
  diagEl("diag-port-wrap").hidden = !params.includes("port");
}

function diagRenderOutput() {
  const box = diagEl("diag-output");
  const job = diagJobs.find((j) => j.id === diagSelectedId);
  if (!job) {
    box.textContent = "No diagnostic selected.";
    return;
  }
  const head = "Job #" + job.id + " - " + diagOpLabel(job.operation) + " - " + job.status;
  if (job.result) {
    box.textContent = head + "\n\n" + job.result.result_summary;
  } else {
    box.textContent = head + "\n\nWaiting for the device to run it...";
  }
}

function diagRenderTable() {
  const body = diagEl("diag-rows");
  body.replaceChildren();

  if (diagJobs.length === 0) {
    const tr = document.createElement("tr");
    const td = diagCell("No diagnostics run yet.");
    td.colSpan = 7;
    tr.appendChild(td);
    body.appendChild(tr);
    return;
  }

  for (const job of diagJobs) {
    const tr = document.createElement("tr");
    if (job.id === diagSelectedId) tr.className = "selected";

    tr.appendChild(diagCell(parseUtc(job.requested_at).toLocaleTimeString()));
    tr.appendChild(diagCell(diagOpLabel(job.operation)));
    tr.appendChild(diagCell(diagParams(job.parameters)));

    const statusTd = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = "badge " + job.status.toLowerCase();
    badge.textContent = job.status;
    statusTd.appendChild(badge);
    tr.appendChild(statusTd);

    if (job.status === "Completed" && job.result) {
      tr.appendChild(job.result.success
        ? diagCell("Passed", "passed")
        : diagCell("Not passed", "notpassed"));
    } else {
      tr.appendChild(diagCell("-"));
    }

    const duration = job.result && job.result.duration != null
      ? job.result.duration.toFixed(1) + " s"
      : "-";
    tr.appendChild(diagCell(duration));

    const viewTd = document.createElement("td");
    const view = document.createElement("button");
    view.type = "button";
    view.className = "link";
    view.textContent = "View";
    view.addEventListener("click", () => {
      diagSelectedId = job.id;
      diagRenderTable();
      diagRenderOutput();
    });
    viewTd.appendChild(view);
    tr.appendChild(viewTd);

    body.appendChild(tr);
  }
}

async function diagLoadJobs() {
  let delay = 10000;
  try {
    diagJobs = await api("/api/devices/" + deviceId + "/diagnostics?limit=10");
    if (diagSelectedId === null && diagJobs.length > 0) diagSelectedId = diagJobs[0].id;

    if (diagWaitingFor !== null) {
      const waiting = diagJobs.find((j) => j.id === diagWaitingFor);
      if (waiting && (waiting.status === "Completed" || waiting.status === "Failed")) {
        diagMessage("Job #" + waiting.id + " " + waiting.status.toLowerCase() + ".", waiting.status === "Failed");
        diagWaitingFor = null;
      }
    }

    diagRenderTable();
    diagRenderOutput();
    if (diagJobs.some((j) => j.status === "Pending" || j.status === "Running")) delay = 2000;
  } catch (err) {
    if (err.message.startsWith("404")) return; // unknown device: stop polling
  }
  diagTimer = setTimeout(diagLoadJobs, delay);
}

async function diagRun() {
  const operation = diagEl("diag-op").value;
  const spec = diagOps[operation];
  if (!spec) return;

  const parameters = {};
  if (spec.params.includes("host")) parameters.host = diagEl("diag-host").value.trim();
  if (spec.params.includes("port")) parameters.port = diagEl("diag-port").value.trim();

  const button = diagEl("diag-run");
  button.disabled = true;
  diagMessage("Sending...", false);
  try {
    const job = await apiPost("/api/devices/" + deviceId + "/diagnostics", { operation, parameters });
    diagSelectedId = job.id;
    diagWaitingFor = job.id;
    diagMessage("Job #" + job.id + " queued. Waiting for the device...", false);
    clearTimeout(diagTimer);
    await diagLoadJobs();
  } catch (err) {
    diagMessage(err.message, true);
  } finally {
    button.disabled = false;
  }
}

async function diagLoadOperations() {
  diagOps = await api("/api/diagnostics/operations");
  const select = diagEl("diag-op");
  select.replaceChildren();
  for (const [name, spec] of Object.entries(diagOps)) {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = spec.label;
    select.appendChild(option);
  }
  diagUpdateFields();
}

async function diagStart() {
  if (!Number.isInteger(deviceId) || deviceId < 1) {
    diagEl("diag-panel").hidden = true;
    return;
  }
  // Handy defaults: the management server itself
  diagEl("diag-host").value = location.hostname;
  diagEl("diag-port").value = location.port || "80";
  diagEl("diag-op").addEventListener("change", diagUpdateFields);
  diagEl("diag-run").addEventListener("click", diagRun);
  try {
    await diagLoadOperations();
  } catch (err) {
    diagMessage("Could not load the operations: " + err.message, true);
    return;
  }
  diagLoadJobs();
}

diagStart();
