# API reference

Interactive documentation is available at `/docs` (Swagger UI) while the server runs.

**Access levels**
- **Public:** no authentication.
- **Agent:** header `X-Agent-Token: <token>`.
- **User:** any logged-in user (session cookie `managit_session`).
- **Admin:** logged-in administrator.

**Common errors:** `401` not authenticated, `403` wrong role, `404` not found, `409` conflict with the current state, `422` invalid input, `429` too many attempts or jobs.

## Public

| Method | Path | Description |
|---|---|---|
| GET | `/health` | `{"status":"ok"}` |
| GET | `/` | Redirects to `/login/` |
| GET | `/login/`, `/admin/`, `/portal/` | Static pages (they contain no data, every API call behind them is protected) |

## Authentication

| Method | Path | Access | Description |
|---|---|---|---|
| POST | `/api/auth/login` | Public | Body `{username, password}`. Sets the session cookie and returns `{username, full_name, role}`. `401` for a wrong login, `429` after 5 failures within 5 minutes |
| POST | `/api/auth/logout` | Public | Deletes the session and the cookie |
| GET | `/api/auth/me` | User | Current user |

## Agent endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/devices/register` | Body: `agent_id`, `hostname`, optional `ip_address`, `os`, `device_type`, `is_simulated`, `department`, `owner`, `agent_version`. Registering an existing `agent_id` updates that device. Returns the device with its `id` |
| POST | `/api/devices/heartbeat` | Body: `device_id`, optional `ip_address`, `cpu_percent`, `memory_percent`, `disk_percent` (each 0 to 100). `404` for an unknown device |
| GET | `/api/agent/jobs?device_id=ID` | Returns the pending jobs `[{id, operation, parameters}]` and marks them Running. A job is never handed out twice |
| POST | `/api/agent/jobs/JOB/result` | Body: `device_id`, `success`, `summary`, optional `duration`, `error`. `403` if the job belongs to another device, `409` if it is not running |

## Devices and monitoring (admin)

| Method | Path | Description |
|---|---|---|
| GET | `/api/devices` | All devices with computed `status` and `latest_metrics` |
| GET | `/api/devices/ID` | One device |
| GET | `/api/devices/ID/metrics?limit=60` | Recent snapshots, newest first (limit 1 to 500) |
| GET | `/api/monitoring/summary` | `total`, `online`, `offline`, `simulated`, `real`, `open_tickets`, `in_progress_tickets`, `resolved_tickets` |

## Diagnostics (admin)

| Method | Path | Description |
|---|---|---|
| GET | `/api/diagnostics/operations` | The five allowed operations and their parameters |
| POST | `/api/devices/ID/diagnostics` | Body `{operation, parameters}`. Returns `201` with a Pending job. `409` if the device is offline, `422` for invalid input, `429` for more than 5 unfinished jobs |
| GET | `/api/devices/ID/diagnostics?limit=20` | Job history of a device (limit 1 to 100) |
| GET | `/api/diagnostics/JOB` | One job with its result |

Operations and parameters:

| Operation | Parameters |
|---|---|
| `ping` | `host` |
| `dns_lookup` | `host` |
| `tcp_check` | `host`, `port` |
| `system_info` | none |
| `resource_check` | none |

A job ends `Completed` when it ran and produced a result (the result's `success` says whether the check passed) and `Failed` when it could not run or timed out.

## Tickets

| Method | Path | Access | Description |
|---|---|---|---|
| GET | `/api/portal/options` | User | Categories and priorities |
| GET | `/api/portal/devices` | User | Admin: all devices. Employee: only their linked device |
| POST | `/api/tickets` | User | Body: `category`, optional `priority` (default Medium), `title` (3 to 150), `description` (10 to 5000), optional `device_id`. The requester comes from the account. `403` if an employee names a device that is not theirs |
| GET | `/api/my/tickets?limit=50` | User | The caller's own tickets |
| GET | `/api/ticket-options` | Admin | Statuses, categories, priorities |
| GET | `/api/tickets?status=Open&limit=100` | Admin | All tickets, newest first |
| GET | `/api/tickets/ID` | Admin | One ticket |
| PATCH | `/api/tickets/ID` | Admin | Any of `status`, `resolution_note`, `device_id`. `422` when resolving without a note or sending an empty body |

Tickets have the reference format `TCK-0001`.
