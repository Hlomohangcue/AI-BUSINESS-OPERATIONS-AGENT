# Developer and Operator Guide

**Status:** Commands and configuration below are grounded in the checked-in files and framework entry points. Commands marked **not executed** were not launched during this audit; the only executed command was the test command listed below.

## Contents

- [Prerequisites](#prerequisites)
- [Environment setup](#environment-setup)
- [Configuration reference](#configuration-reference)
- [Safe local startup](#safe-local-startup)
- [Tests and logs](#tests-and-logs)
- [Database and workflow operations](#database-and-workflow-operations)
- [Troubleshooting and shutdown](#troubleshooting-and-shutdown)

## Prerequisites

- Python and the pinned dependencies in [`requirements.txt`](../../requirements.txt).
- Python 3.11 or newer is implied by `enum.StrEnum` in the authorization module; the project does not declare a formal supported-version range.
- Access to Gemini credentials supported by the installed Google ADK/GenAI libraries to use live AI chat. The repository does not document or validate a specific credential setup.
- The application’s sample CSVs under `src/data/` for demonstration reporting.

The repository does not declare a `requires-python` value, a supported Python-version matrix, a README, or a dependency installation script.

## Environment setup

The following uses conventional Python virtual-environment and pip commands, derived from the requirements file. **Documented from configuration; not executed during audit.**

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Do not copy the ignored `.env` file into source control or paste its contents into tickets/logs. This audit did not read its values.

## Configuration reference

| Variable | Used by | Purpose |
|---|---|---|
| `BUSINESS_OPERATIONS_API_URL` | `dashboard.py` | API base URL; defaults in code to loopback `http://127.0.0.1:8000`. |
| `BUSINESS_OPERATIONS_API_TOKEN` | `dashboard.py` | Dashboard bearer credential; chat submission is disabled when absent. |
| `BUSINESS_OPERATIONS_API_TOKENS_JSON` | `src/api/main.py` | Server-side JSON token registry mapping credentials to user, organization, and role. Never put real values in docs or source. |
| `WORKFLOW_DB_PATH` | `src/workflows/actions.py` | Optional SQLite path override; defaults to repository `data/workflow_actions.db`. |

The agent configures primary model `gemini-flash-lite-latest` and fallback model `gemini-3.5-flash` in [`business_operations_agent.py`](../../src/agents/business_operations_agent.py); there is no model-name environment variable in the inspected source. Google provider authentication is delegated to the ADK/GenAI runtime and is not configured by a repository setup guide.

## Safe local startup

Run the API and dashboard in separate terminals. These standard framework entry-point commands are **documented from configuration; not executed during audit**:

```powershell
.\.venv\Scripts\python.exe -m uvicorn src.api.main:app --reload
```

```powershell
.\.venv\Scripts\streamlit.exe run dashboard.py
```

The report-only dashboard can display repository demonstration data without live chat credentials. Chat requires a configured dashboard token and a matching server-side token mapping. Do not expose the development token configuration to an untrusted network. The project’s API code explicitly describes this mapping as a development bootstrap.

Multipart chat uploads are limited to 5 MiB per CSV. The API performs a bounded application read and closes parsed form files, but multipart parsing occurs first and may spool content to temporary storage; deployments still need an aggregate request-body and temporary-storage limit at the server or proxy layer.

## Tests and logs

**Executed and verified during this audit:**

```powershell
.\.venv\Scripts\pytest.exe -q
```

Result: `73 passed, 6 warnings in 16.87s` (original baseline: `58 passed, 4 warnings`). `tests/conftest.py` directs each test to a temporary SQLite file. The API chat tests replace the agent runner for uploaded-data scenarios; model fallback tests use fakes. No live model call was part of the test run.

The API uses Python’s standard `logging` logger in `src.api.main`; an unexpected agent exception is logged with `logger.exception`. No logging configuration, log destination, rotation, or monitoring setup was found in the repository. Streamlit displays user-facing errors and, for report-loading errors, a technical-details expander. Avoid putting tokens, full uploaded business files, or customer data into logs.

## Database and workflow operations

The SQLite file is opened lazily by workflow operations. The existing local database was inspected read-only for schema and aggregate status/provenance counts only; no row values or identities were retrieved, and no writes were made. At inspection time, 10 pending actions lacked a creation event; these and any action without exactly one non-empty `ACTION_CREATED` actor event cannot be approved automatically. Reconcile proposer identity through an approved operational process rather than assigning an inference. No migration command, backup command, scheduled backup, retention setting, or restore utility was found.

Before using any workflow API, verify that `WORKFLOW_DB_PATH` points to an intended local/test location and that the process account has appropriate filesystem access. Do not copy the database into documentation or share it as a troubleshooting artifact; it can contain organization-linked action reasons and actor IDs.

The API workflow status `EXECUTED` is a local simulated action record. It does not mean a supplier order was sent or fulfilled. The dashboard currently has no action approval/execution screen.

## Troubleshooting and shutdown

| Symptom | Evidence-based check |
|---|---|
| Dashboard report fails | Confirm all three uploaded CSVs are present, have the required columns, and pass numeric/unique-key validation; otherwise remove all uploads for sample-data mode. |
| Dashboard chat unavailable | Check whether `BUSINESS_OPERATIONS_API_TOKEN` is configured in the dashboard process; verify API URL and that its token registry has a corresponding actor. Do not print token values. |
| API returns `503` for workflow/chat | Check presence and valid JSON structure of `BUSINESS_OPERATIONS_API_TOKENS_JSON` in the API process environment. |
| API returns `403` | Check the configured actor role against the permissions table in [API and data model](API_AND_DATA_MODEL.md#authentication-and-authorization). |
| API returns `409` | Action is not in the required state, proposer provenance is unavailable, or the proposer is attempting self-approval; inspect the action and events through authenticated GET endpoints. Do not assign an inferred proposer. |
| Agent returns `500`/`502` | Review API logs for the generic request failure context; check provider availability/credential configuration without exposing credentials. |
| SQLite cannot open/write | Check the configured DB path, directory permissions, and whether another process is holding a write lock. No automated recovery tool is included. |

Stop local API and Streamlit processes with `Ctrl+C` in their respective terminals. No persistent external operation is performed by stopping these processes. The in-memory conversation context is lost on API restart.
