# Test plan and results

## Scope
The tests check the full workflow (device, heartbeat, diagnostic, ticket, resolution) and the security rules (authentication, roles, validation, brute force).

## Environment
- Linux VM (VirtualBox) running the API at `192.168.56.10:8000`
- Windows PC running the real agent and the simulator
- Test date: 2026-11-08

## Automated API tests
Script: [`tests/e2e_api.py`](../tests/e2e_api.py). It uses only the Python standard library, asks for the admin and employee passwords with hidden input, and never prints or stores passwords or the agent token. Test data is prefixed with `[E2E]` or `e2e-test-device`, so it can be cleaned up afterwards.

Run it on the server, from the project root, with the API, the agent and the simulator running:

```bash
python3 tests/e2e_api.py
```

| Area | What is checked |
|---|---|
| Health and login | Health endpoint, wrong password, unknown user (same message), correct login, `HttpOnly` and `SameSite` cookie |
| Access control | Anonymous users get 401 and employees get 403 on admin endpoints, admins get 200 |
| Agent API | Token required for register and heartbeat, no duplicate device for the same `agent_id`, online status, latest metrics, invalid values (422), unknown device (404) |
| Diagnostics | Rejection of an unknown operation, option injection, command injection, bad ports, extra or missing parameters. Job lifecycle (Pending, Running, Completed), no double hand-out, wrong-device result refused, offline device refused, a real agent run, a labelled simulated run |
| Tickets | Identity taken from the account, own-device rule, validation, HTML stored as plain text, own tickets only, admin-only reads and updates, resolution note required, employee sees the resolution |
| Summary | Counts consistent with the device list, ticket counts present |
| Logout and brute force | Old session invalid after logout, lockout after 5 failed logins |

The result of each run is written to [`test-results.txt`](test-results.txt).

## Manual tests

| ID | Scenario | Expected | Result |
|---|---|---|---|
| M1 | Stop the agent, wait about 100 seconds | The device turns offline on the dashboard. It returns to online after the agent restarts | Pass |
| M2 | Stop the API while the agent runs, then restart it | The agent logs retries and keeps running, the dashboard shows an error banner, everything recovers by itself, and the user is still logged in | Pass |
| M3 | Set a wrong `agent_token` on the agent | The agent logs a critical message and exits | Pass |
| M4 | Full demo: employee submits a ticket, admin runs a diagnostic, resolves with a note, employee sees the resolution | The whole flow works in the browser | Pass |
| M5 | Log out then use the back button. Open `/admin/` as an employee | The login page appears and no data is shown. The employee is redirected to the portal | Pass |

## Cleaning up test data
The script leaves one test device and a few `[E2E]` tickets. Remove them with the SQL in the project notes, or ignore them.

## Latest recorded run

```text
ManaGit end-to-end API test run: 2026-11-08 15:25
Result: 67 passed, 0 failed, 0 skipped
```

The full list is in [test-results.txt](test-results.txt).
