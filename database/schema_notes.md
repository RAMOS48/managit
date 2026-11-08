# Database notes

SQLite file: `database/it_platform.db`. It is created automatically when the API first starts and is **not committed** (see `.gitignore`).

| Table | Purpose | Main columns |
|---|---|---|
| `devices` | Inventory | `hostname`, `agent_id` (unique per agent), `ip_address`, `os`, `device_type`, `is_simulated`, `department`, `owner`, `agent_version`, `created_at`, `last_seen` |
| `metric_snapshots` | CPU, RAM and disk history | `device_id`, `cpu_percent`, `memory_percent`, `disk_percent`, `collected_at` (kept 7 days) |
| `users` | Accounts | `username` (unique), `full_name`, `password_hash` (scrypt), `role` (`admin` or `employee`), `linked_device_id` |
| `user_sessions` | Login sessions | `token_hash` (SHA-256, unique), `user_id`, `created_at`, `expires_at` |
| `tickets` | Support requests | `requester_id`, `requester_name`, `device_id`, `category`, `priority`, `title`, `description`, `status`, `resolution_note`, `created_at`, `updated_at` |
| `diagnostic_jobs` | Requested diagnostics | `device_id`, `requested_by`, `operation`, `parameters` (JSON text), `status`, `requested_at`, `completed_at` |
| `diagnostic_results` | Outcome of a job | `job_id`, `result_summary`, `success`, `duration`, `created_at` |

## Value sets
- Ticket status: `Open`, `In Progress`, `Resolved`
- Ticket category: `Network`, `Hardware`, `Software`, `Account/access`, `Other`
- Ticket priority: `Low`, `Medium`, `High`
- Job status: `Pending`, `Running`, `Completed`, `Failed`
- Device status (computed, not stored): `online` or `offline`

## Notes
- Timestamps are stored as naive UTC.
- Tables are created by SQLAlchemy at startup. The project has no migration tool, so changing an existing column needs a manual `ALTER TABLE` (used twice during development: `tickets.requester_name` and `users.full_name`).
- Users are created with `backend/create_user.py`, which asks for the password interactively.
