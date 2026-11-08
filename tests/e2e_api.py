#!/usr/bin/env python3
"""End-to-end API tests for ManaGit (standard library only).

Run on the Linux server, from the project root, with Uvicorn running:
    python3 tests/e2e_api.py

It asks for the admin and employee passwords (hidden), never prints or stores
them or the agent token, and writes a summary to docs/test-results.txt.
Test data is prefixed with [E2E] / e2e-test-device so it can be cleaned up.
"""
import getpass
import http.cookiejar
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8000"
ENV_FILE = ROOT / "backend" / ".env"
RESULTS_FILE = ROOT / "docs" / "test-results.txt"

results = []
counter = 0


def next_id():
    global counter
    counter += 1
    return "T%02d" % counter


def check(description, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    test_id = next_id()
    results.append((test_id, description, status, detail))
    line = "[%s] %s %s" % (status, test_id, description)
    if not condition and detail:
        line += "  -> " + detail
    print(line)
    return bool(condition)


def skip(description, reason):
    test_id = next_id()
    results.append((test_id, description, "SKIP", reason))
    print("[SKIP] %s %s  -> %s" % (test_id, description, reason))


def finish(exit_code=None):
    passed = sum(1 for r in results if r[2] == "PASS")
    failed = sum(1 for r in results if r[2] == "FAIL")
    skipped = sum(1 for r in results if r[2] == "SKIP")
    lines = [
        "ManaGit end-to-end API test run: " + datetime.now().strftime("%Y-%m-%d %H:%M"),
        "Result: %d passed, %d failed, %d skipped" % (passed, failed, skipped),
        "",
    ]
    for test_id, description, status, detail in results:
        line = "[%s] %s %s" % (status, test_id, description)
        if status != "PASS" and detail:
            line += "  -> " + detail
        lines.append(line)
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n%d passed, %d failed, %d skipped" % (passed, failed, skipped))
    print("Summary written to " + str(RESULTS_FILE.relative_to(ROOT)))
    sys.exit(exit_code if exit_code is not None else (1 if failed else 0))


class Client:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def call(self, method, path, body=None, headers=None):
        """Returns (status, json_or_None, set_cookie_headers)."""
        data = None
        hdrs = {"Accept": "application/json"}
        if body is not None:
            data = json.dumps(body).encode()
            hdrs["Content-Type"] = "application/json"
        if headers:
            hdrs.update(headers)
        request = urllib.request.Request(BASE + path, data=data, method=method, headers=hdrs)
        try:
            response = self.opener.open(request, timeout=15)
        except urllib.error.HTTPError as err:
            response = err
        raw = response.read()
        try:
            payload = json.loads(raw) if raw else None
        except ValueError:
            payload = None
        cookies = response.headers.get_all("Set-Cookie") or []
        return response.getcode(), payload, cookies


def detail_of(payload):
    if isinstance(payload, dict):
        value = payload.get("detail")
        return value if isinstance(value, str) else json.dumps(value)
    return ""


def load_agent_token():
    if not ENV_FILE.exists():
        sys.exit("%s not found" % ENV_FILE)
    for line in ENV_FILE.read_text().splitlines():
        if line.startswith("AGENT_TOKEN="):
            return line.split("=", 1)[1].strip()
    sys.exit("AGENT_TOKEN not found in backend/.env")


def wait_for_job(admin, job_id, timeout=45):
    deadline = time.time() + timeout
    job = None
    while time.time() < deadline:
        status, job, _ = admin.call("GET", "/api/diagnostics/%d" % job_id)
        if status == 200 and job["status"] in ("Completed", "Failed"):
            return job
        time.sleep(3)
    return job


def main():
    token = load_agent_token()
    agent = {"X-Agent-Token": token}
    bad_agent = {"X-Agent-Token": "wrong-token"}

    admin_user = input("Admin username [admin]: ").strip() or "admin"
    admin_pw = getpass.getpass("Admin password: ")
    emp_user = input("Employee username [employee1]: ").strip() or "employee1"
    emp_pw = getpass.getpass("Employee password: ")
    print()

    anon, admin, emp = Client(), Client(), Client()

    # ---------- 1. Health and authentication ----------
    print("--- Health and authentication ---")
    status, body, _ = anon.call("GET", "/health")
    check("Health endpoint answers", status == 200 and body == {"status": "ok"}, "status %s" % status)

    status, wrong_body, _ = anon.call("POST", "/api/auth/login",
                                      {"username": admin_user, "password": "definitely-wrong-password"})
    check("Wrong password is rejected (401)", status == 401, "status %s" % status)
    status, unknown_body, _ = anon.call("POST", "/api/auth/login",
                                        {"username": "e2e-nobody", "password": "definitely-wrong-password"})
    check("Unknown user gets the same message as a wrong password",
          status == 401 and detail_of(wrong_body) == detail_of(unknown_body) and detail_of(wrong_body) != "",
          "status %s" % status)

    status, body, cookies = admin.call("POST", "/api/auth/login",
                                       {"username": admin_user, "password": admin_pw})
    if not check("Admin can log in", status == 200 and isinstance(body, dict) and body.get("role") == "admin",
                 "status %s" % status):
        print("Cannot continue without an admin session. Check the username and password.")
        finish(1)
    cookie_text = " ".join(cookies).lower()
    check("Session cookie is HttpOnly with SameSite", "httponly" in cookie_text and "samesite" in cookie_text)

    status, body, _ = emp.call("POST", "/api/auth/login", {"username": emp_user, "password": emp_pw})
    if not check("Employee can log in", status == 200 and isinstance(body, dict) and body.get("role") == "employee",
                 "status %s" % status):
        print("Cannot continue without an employee session. Check the username and password.")
        finish(1)

    check("Logged-in user can read /api/auth/me", admin.call("GET", "/api/auth/me")[0] == 200)
    check("Anonymous /api/auth/me is refused (401)", anon.call("GET", "/api/auth/me")[0] == 401)

    # ---------- 2. Access control ----------
    print("\n--- Access control ---")
    admin_paths = ["/api/devices", "/api/monitoring/summary", "/api/tickets", "/api/diagnostics/operations"]
    codes = [anon.call("GET", p)[0] for p in admin_paths]
    check("Anonymous users are blocked from admin endpoints (401)", all(c == 401 for c in codes), str(codes))
    codes = [emp.call("GET", p)[0] for p in admin_paths]
    check("Employees are blocked from admin endpoints (403)", all(c == 403 for c in codes), str(codes))
    codes = [admin.call("GET", p)[0] for p in admin_paths]
    check("Admin can use admin endpoints (200)", all(c == 200 for c in codes), str(codes))
    check("Anonymous users cannot use the portal endpoints (401)",
          anon.call("GET", "/api/portal/devices")[0] == 401)

    # ---------- 3. Agent API ----------
    print("\n--- Agent API ---")
    reg = {"agent_id": "e2e-test-device", "hostname": "E2E-TEST-01", "ip_address": "192.168.56.250",
           "os": "E2E OS", "device_type": "pc", "is_simulated": True, "department": "QA",
           "owner": "E2E Tests", "agent_version": "e2e-0.1"}
    check("Registration without a token is refused (401)",
          anon.call("POST", "/api/devices/register", reg)[0] == 401)
    check("Registration with a wrong token is refused (401)",
          anon.call("POST", "/api/devices/register", reg, bad_agent)[0] == 401)
    status, body, _ = anon.call("POST", "/api/devices/register", reg, agent)
    if not check("Registration with the agent token works",
                 status == 200 and isinstance(body, dict) and "id" in body, "status %s" % status):
        finish(1)
    dev_id = body["id"]
    status, again, _ = anon.call("POST", "/api/devices/register", reg, agent)
    check("Registering the same agent_id again does not duplicate the device",
          status == 200 and again["id"] == dev_id)

    heartbeat = {"device_id": dev_id, "cpu_percent": 12.5, "memory_percent": 40.0, "disk_percent": 55.0}
    check("Heartbeat with the token works", anon.call("POST", "/api/devices/heartbeat", heartbeat, agent)[0] == 200)
    check("Heartbeat without a token is refused (401)",
          anon.call("POST", "/api/devices/heartbeat", heartbeat)[0] == 401)
    status, device, _ = admin.call("GET", "/api/devices/%d" % dev_id)
    metrics = device.get("latest_metrics") if isinstance(device, dict) else None
    check("Device shows online with its latest metrics",
          status == 200 and device["status"] == "online" and metrics is not None and metrics["cpu_percent"] == 12.5)
    check("Heartbeat with CPU 150 is rejected (422)",
          anon.call("POST", "/api/devices/heartbeat", dict(heartbeat, cpu_percent=150), agent)[0] == 422)
    check("Heartbeat for an unknown device is rejected (404)",
          anon.call("POST", "/api/devices/heartbeat", dict(heartbeat, device_id=999999), agent)[0] == 404)
    status, history, _ = admin.call("GET", "/api/devices/%d/metrics?limit=5" % dev_id)
    check("Metrics history returns the snapshots", status == 200 and isinstance(history, list) and len(history) >= 1)

    # ---------- 4. Diagnostics ----------
    print("\n--- Diagnostics ---")
    diag_url = "/api/devices/%d/diagnostics" % dev_id
    bad_requests = [
        ("unknown operation", {"operation": "run_command", "parameters": {"host": "1.1.1.1"}}),
        ("option injection in host", {"operation": "ping", "parameters": {"host": "-n 5000"}}),
        ("command injection in host", {"operation": "ping", "parameters": {"host": "1.1.1.1; dir"}}),
        ("port out of range", {"operation": "tcp_check", "parameters": {"host": "1.1.1.1", "port": 70000}}),
        ("unexpected parameter", {"operation": "system_info", "parameters": {"host": "1.1.1.1"}}),
        ("missing parameter", {"operation": "ping", "parameters": {}}),
    ]
    for label, payload in bad_requests:
        status = admin.call("POST", diag_url, payload)[0]
        check("Diagnostics reject: %s (422)" % label, status == 422, "status %s" % status)

    status, job, _ = admin.call("POST", diag_url, {"operation": "ping", "parameters": {"host": "127.0.0.1"}})
    created = status == 201 and isinstance(job, dict) and job.get("status") == "Pending"
    check("Admin can create a diagnostic job (Pending)", created, "status %s" % status)
    status, devices, _ = admin.call("GET", "/api/devices")
    if created:
        job_id = job["id"]
        poll = "/api/agent/jobs?device_id=%d" % dev_id
        check("Job polling without a token is refused (401)", anon.call("GET", poll)[0] == 401)
        status, jobs, _ = anon.call("GET", poll, headers=agent)
        check("Agent can claim the pending job",
              status == 200 and isinstance(jobs, list) and any(j["id"] == job_id for j in jobs))
        status, second, _ = anon.call("GET", poll, headers=agent)
        check("A claimed job is not handed out twice", status == 200 and second == [])
        status, current, _ = admin.call("GET", "/api/diagnostics/%d" % job_id)
        check("A claimed job shows as Running", status == 200 and current["status"] == "Running")

        result = {"device_id": dev_id, "success": True, "summary": "E2E fake result",
                  "duration": 0.1, "error": False}
        others = [d for d in devices if d["id"] != dev_id]
        result_url = "/api/agent/jobs/%d/result" % job_id
        if others:
            status = anon.call("POST", result_url, dict(result, device_id=others[0]["id"]), agent)[0]
            check("A result for another device's job is refused (403)", status == 403, "status %s" % status)
        else:
            skip("A result for another device's job is refused (403)", "no other device exists")
        check("Agent can submit the result", anon.call("POST", result_url, result, agent)[0] == 200)
        status, final, _ = admin.call("GET", "/api/diagnostics/%d" % job_id)
        res = final.get("result") if isinstance(final, dict) else None
        check("Job ends as Completed with its result",
              status == 200 and final["status"] == "Completed" and res is not None
              and res["result_summary"] == "E2E fake result")
        check("A second result for the same job is refused (409)",
              anon.call("POST", result_url, result, agent)[0] == 409)

    offline = [d for d in devices if d["status"] == "offline"]
    if offline:
        status = admin.call("POST", "/api/devices/%d/diagnostics" % offline[0]["id"],
                            {"operation": "system_info", "parameters": {}})[0]
        check("Diagnostics cannot target an offline device (409)", status == 409, "status %s" % status)
    else:
        skip("Diagnostics cannot target an offline device (409)", "no offline device available")

    real = [d for d in devices if not d["is_simulated"] and d["status"] == "online"]
    if real:
        status, rjob, _ = admin.call("POST", "/api/devices/%d/diagnostics" % real[0]["id"],
                                     {"operation": "system_info", "parameters": {}})
        if status == 201:
            done = wait_for_job(admin, rjob["id"])
            res = done.get("result") if isinstance(done, dict) else None
            check("The real agent runs a diagnostic and reports back",
                  res is not None and done["status"] == "Completed" and res["success"]
                  and res["result_summary"].startswith("Hostname:"),
                  "job status %s" % (done["status"] if isinstance(done, dict) else "none"))
        else:
            check("The real agent runs a diagnostic and reports back", False, "create status %s" % status)
    else:
        skip("The real agent runs a diagnostic and reports back", "no online real device (start the agent)")

    sims = [d for d in devices if d["is_simulated"] and d["status"] == "online"
            and d["agent_id"] != "e2e-test-device"]
    if sims:
        status, sjob, _ = admin.call("POST", "/api/devices/%d/diagnostics" % sims[0]["id"],
                                     {"operation": "ping", "parameters": {"host": "127.0.0.1"}})
        if status == 201:
            done = wait_for_job(admin, sjob["id"])
            res = done.get("result") if isinstance(done, dict) else None
            check("A simulated device answers with a labelled fake result",
                  res is not None and done["status"] == "Completed"
                  and res["result_summary"].startswith("[SIMULATED]"),
                  "job status %s" % (done["status"] if isinstance(done, dict) else "none"))
        else:
            check("A simulated device answers with a labelled fake result", False, "create status %s" % status)
    else:
        skip("A simulated device answers with a labelled fake result",
             "no online simulated device (start the simulator)")

    # ---------- 5. Tickets ----------
    print("\n--- Tickets ---")
    status, my_devices, _ = emp.call("GET", "/api/portal/devices")
    check("Employee sees at most their own device in the form",
          status == 200 and isinstance(my_devices, list) and len(my_devices) <= 1)
    own_id = my_devices[0]["id"] if isinstance(my_devices, list) and my_devices else None

    ticket_body = {"requester_name": "Hacker", "device_id": own_id, "category": "Network",
                   "priority": "High", "title": "[E2E] Cannot access shared folders",
                   "description": "End-to-end test ticket: cannot open the shared folders."}
    status, ticket, _ = emp.call("POST", "/api/tickets", ticket_body)
    if not check("Employee can create a ticket", status == 201 and isinstance(ticket, dict), "status %s" % status):
        finish(1)
    tid = ticket["id"]
    check("Ticket identity comes from the account, not the form", ticket["requester_name"] != "Hacker")
    check("Ticket gets a reference and starts Open",
          ticket["reference"].startswith("TCK-") and ticket["status"] == "Open")

    other_devices = [d for d in devices if d["id"] != own_id]
    if other_devices:
        status = emp.call("POST", "/api/tickets", dict(ticket_body, device_id=other_devices[0]["id"]))[0]
        check("Employee cannot file a ticket about someone else's device (403)", status == 403,
              "status %s" % status)
    else:
        skip("Employee cannot file a ticket about someone else's device (403)", "no other device exists")

    valid = {"category": "Other", "title": "[E2E] valid title",
             "description": "A long enough description for validation."}
    check("Invalid category is rejected (422)", emp.call("POST", "/api/tickets", dict(valid, category="Hacking"))[0] == 422)
    check("Invalid priority is rejected (422)", emp.call("POST", "/api/tickets", dict(valid, priority="Urgent"))[0] == 422)
    check("Too short title is rejected (422)", emp.call("POST", "/api/tickets", dict(valid, title="ab"))[0] == 422)
    check("Too short description is rejected (422)",
          emp.call("POST", "/api/tickets", dict(valid, description="short"))[0] == 422)
    xss_title = "[E2E] <b>bold</b>"
    status, xss, _ = emp.call("POST", "/api/tickets", dict(valid, title=xss_title))
    check("HTML in a title is stored as plain text", status == 201 and xss["title"] == xss_title)

    status, mine, _ = emp.call("GET", "/api/my/tickets")
    check("Employee sees their ticket in My tickets",
          status == 200 and isinstance(mine, list) and any(t["id"] == tid for t in mine))
    check("Employee cannot read tickets through admin endpoints (403)",
          emp.call("GET", "/api/tickets/%d" % tid)[0] == 403)
    check("Employee cannot update tickets (403)",
          emp.call("PATCH", "/api/tickets/%d" % tid, {"status": "Resolved", "resolution_note": "x"})[0] == 403)
    check("Employee cannot request diagnostics (403)",
          emp.call("POST", diag_url, {"operation": "system_info", "parameters": {}})[0] == 403)

    status, listing, _ = admin.call("GET", "/api/tickets?limit=500")
    check("Admin sees the ticket in the list",
          status == 200 and isinstance(listing, list) and any(t["id"] == tid for t in listing))
    ticket_url = "/api/tickets/%d" % tid
    check("Resolving without a note is refused (422)", admin.call("PATCH", ticket_url, {"status": "Resolved"})[0] == 422)
    check("Invalid status is refused (422)", admin.call("PATCH", ticket_url, {"status": "Closed"})[0] == 422)
    check("Empty update is refused (422)", admin.call("PATCH", ticket_url, {})[0] == 422)
    check("Updating an unknown ticket gives 404",
          admin.call("PATCH", "/api/tickets/999999", {"status": "Open"})[0] == 404)
    status, upd, _ = admin.call("PATCH", ticket_url, {"status": "In Progress"})
    check("Admin can set the ticket In Progress", status == 200 and upd["status"] == "In Progress")
    status, upd, _ = admin.call("PATCH", ticket_url, {"status": "Resolved",
                                                      "resolution_note": "E2E: re-mapped the network drive."})
    check("Admin can resolve the ticket with a note", status == 200 and upd["status"] == "Resolved")
    status, mine, _ = emp.call("GET", "/api/my/tickets")
    seen = next((t for t in mine if t["id"] == tid), None) if isinstance(mine, list) else None
    check("Employee sees the resolution",
          seen is not None and seen["status"] == "Resolved" and "re-mapped" in (seen["resolution_note"] or ""))

    # ---------- 6. Summary ----------
    print("\n--- Monitoring summary ---")
    status, summary, _ = admin.call("GET", "/api/monitoring/summary")
    status2, devices_now, _ = admin.call("GET", "/api/devices")
    check("Summary counts are consistent with the device list",
          status == 200 and status2 == 200 and summary["total"] == len(devices_now)
          and summary["online"] + summary["offline"] == summary["total"])
    check("Summary includes ticket counts", summary.get("resolved_tickets", 0) >= 1
          and "open_tickets" in summary and "in_progress_tickets" in summary)

    # ---------- 7. Logout and brute force ----------
    print("\n--- Logout and brute-force protection ---")
    old_cookies = [c for c in emp.jar if c.name == "managit_session"]
    check("Employee can log out", emp.call("POST", "/api/auth/logout")[0] == 200)
    replay = Client()
    for cookie in old_cookies:
        replay.jar.set_cookie(cookie)
    check("The old session token is invalid after logout (401)", replay.call("GET", "/api/auth/me")[0] == 401)
    admin.call("POST", "/api/auth/logout")

    codes = [anon.call("POST", "/api/auth/login", {"username": "e2e-locktest", "password": "bad"})[0]
             for _ in range(6)]
    check("Login is locked after 5 failed attempts (429 on the 6th)", codes == [401] * 5 + [429], str(codes))

    finish()


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as exc:
        print("Cannot reach the server at %s: %s" % (BASE, exc))
        sys.exit(2)
