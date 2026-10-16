# Testing and Security Audit

**Audit date:** 2026-10-15

**Method:** Source review, focused regression tests, and a full pytest run against test-isolated temporary SQLite databases. The existing SQLite database was inspected read-only for schema and aggregate status/provenance counts; no row values or identities were retrieved and no database writes were made. No live Gemini request or real business action was performed.

## Contents

- [Test architecture and status](#test-architecture-and-status)
- [Coverage matrix](#coverage-matrix)
- [Findings](#findings)
- [Unverified assumptions](#unverified-assumptions)
- [Recommended tests](#recommended-tests)

## Test architecture and status

The project uses pytest, configured in [`pyproject.toml`](../../pyproject.toml) to use the repository root on the Python path and discover `tests/`. `tests/conftest.py` sets `WORKFLOW_DB_PATH` to a `tmp_path` per test. The API tests use FastAPI `TestClient`; the agent chat upload test monkeypatches the ADK runner. Model fallback tests use fake models. Reconciliation tests load repository sample CSVs read-only.

**Original baseline:** `.\.venv\Scripts\python.exe -m pytest -q` — **58 passed**, **4 warnings**, 24.74 seconds. **Final verification:** the same command — **73 passed**, **6 warnings**, 16.87 seconds. The six warnings are dependency/framework deprecations and a future-compatibility warning (Starlette/AnyIO, Google GenAI typing, Google Cloud Storage compatibility, and FastAPI's 422 status constant). The focused remediation suites also passed: **54 passed**, **6 warnings**, 14.28 seconds. Pytest uses the per-test temporary database from `tests/conftest.py`, not the pre-existing `data/workflow_actions.db`; no external model call was made.

The UI was not browser-tested; no live server, production data, or deployment was exercised. Test success is evidence for the present suite only, not a security certification or production readiness claim.

## Coverage matrix

| Component | Existing test evidence | Important gaps | Recommended next test |
|---|---|---|---|
| Reconciliation engine | `tests/test_reconciliation.py`: match, mismatch, missing, orphan, low stock, entity lookup, JSON-safe report | Duplicate inputs at engine layer; exact one-cent behavior; currency rounding | Table-driven boundary/duplicate tests using synthetic frames |
| Business priorities | `tests/test_business_rules.py` and `tests/test_reconciliation.py`: mismatch/missing, inventory priorities, and below/equal/above/zero threshold behavior | Duplicate inputs at engine layer; exact one-cent behavior; currency rounding | Table-driven boundary/duplicate tests using synthetic frames |
| Upload validation | `tests/test_uploads.py` and `tests/test_api.py`: required fields, duplicate IDs, invalid numbers, partial uploads, malformed multipart CSV, exact per-file boundary, oversized file rejection, bounded read when size is unavailable, and multipart cleanup | Aggregate body and temporary-storage limits, encodings, very wide/long CSVs, extra columns policy | Configure and test request/body/temp-storage limits at the serving or proxy layer |
| Agent data context/tools | `tests/test_uploaded_agent_tools.py`: uploaded datasets reach report/entity tools | Concurrent request isolation under real ASGI concurrency; model output correctness | Concurrent async API test with distinct synthetic tenant datasets |
| API/auth | `tests/test_api.py`: missing/invalid tokens, missing/malformed token registry, role checks, body identity spoofing, transition conflict, tenant hiding, and upload handling | Token rotation, request rate/body limits, all role/route combinations, real model integration | Parameterized auth and validation matrix; mock provider integration contract |
| Workflow persistence | `tests/test_workflows.py`: lifecycle, repeat transitions, role/tenant restrictions, event provenance, self-approval denial, and legacy unknown-proposer denial | Cross-process concurrency, DB migration variants, direct event tampering, disk/backup failures | Temporary-file concurrency and migration tests |
| Gemini fallback | `tests/test_model_fallback.py`: success, fallback, fallback error, partial-output no-retry | Provider configuration, quota/timeouts, tool-call compatibility against live models | Recorded/mock response contract test and separately controlled integration test |
| Dashboard | No dashboard-specific test file found | UI states, hidden/invalid token, HTTP errors, upload/report equivalence, accessibility | Streamlit AppTest or browser smoke test with mocked API |
| CI/deployment | No tracked `.github` workflow or deployment configuration found | Reproducible CI and deploy gates | Add a CI workflow after choosing supported Python versions and deployment target |

## Findings

The following are source-review findings, not exploit attempts. Status reflects remediation in this checkout; severity describes residual potential impact.

| ID | Severity | Status | Evidence | Why it matters / remediation |
|---|---|---|---|---|
| AUD-01 | **Medium** | Remediated | [`engine.py`](../../src/reconciliation/engine.py): inventory lookup now uses `<=` for `LOW_STOCK`; synthetic regression tests cover zero, below, equal, and above threshold in report and lookup. `below_reorder_level` intentionally remains strict `<`. | The prior report/lookup equality mismatch is fixed and tested. |
| AUD-02 | **Medium** | Partially remediated | [`src/api/main.py`](../../src/api/main.py): rejects parser-reported sizes above 5 MiB per file, bounds reads to at most 5 MiB plus one byte, and closes multipart form resources. Tests cover size boundary, oversized input, unknown size, and cleanup. | The API handler no longer makes an unbounded application-level `UploadFile.read()`. `request.form()` parses first and can spool to temporary storage; no aggregate request-body or temporary-storage cap is configured. Set limits at the server/proxy layer before public use. |
| AUD-03 | **Medium** | Confirmed deployment limitation; regression tests added | [`get_authenticated_actor()`](../../src/api/main.py): process environment JSON maps bearer tokens to actors; API module docstring explicitly calls this a development bootstrap. Tests verify missing/malformed registry fails closed and request body identity fields do not override the authenticated actor. | Token distribution, revocation, rotation, auditability, and identity lifecycle remain manual. Integrate a supported identity provider and managed secrets before external exposure. |
| AUD-04 | **Medium** | Proposer-to-approver separation remediated; legacy provenance limitation remains | [`actions.py`](../../src/workflows/actions.py): approval requires exactly one non-empty creation-event actor different from the authenticated approver. Tests cover same-actor denial and missing provenance. | A proposer cannot approve their own action, including as administrator. Read-only aggregate inspection found 10 pending actions without creation events; these fail closed and need manual reconciliation. Execution is not required to be a third distinct actor. |
| AUD-05 | **Medium** | Suspected design risk | [`business_operations_agent.py`](../../src/agents/business_operations_agent.py) gives strong factuality instructions, and upload values flow into tool outputs; no explicit prompt-injection filtering/trust-boundary defense was found. | Untrusted CSV cells or user text may influence the model. Treat all user/file text as untrusted, constrain tool permissions, and evaluate hostile-content cases; prompt text alone is not a security boundary. |
| AUD-06 | **Low** | Confirmed schema limitation | [`actions.py`](../../src/workflows/actions.py): event rows are inserted by application code, but the schema declares no FK, update/delete trigger, or append-only enforcement. | Application routes provide read access but local DB operators can alter event records. Consider stronger database controls, access restrictions, external append-only logging, and integrity monitoring. |
| AUD-07 | **Low** | Confirmed functional scope | [`actions.py`](../../src/workflows/actions.py) permits only pending → approved → executed; API returns an explicit simulated-execution note. | No reject/cancel/retry or external operation exists. Do not treat `EXECUTED` as supplier fulfillment; define states and reconciliation before integrating a side effect. |
| AUD-08 | **Informational** | Confirmed operational limitation | [`src/api/main.py`](../../src/api/main.py) configures `InMemorySessionService`; the comment notes conversations are lost on restart. | Chat history is not durable. Use durable storage only if retention, privacy, and deletion requirements are defined. |

### Additional security observations

- SQL statements use bound parameters for values; no string-built SQL query was found in the workflow path.
- Authenticated workflow reads and writes filter by organization ID. API tests include a cross-organization read-denial case.
- Actor identity is derived from configured credentials, placed in a `ContextVar`, and reset after agent execution. Uploaded datasets are also request-scoped, copied, and reset in a `finally` block.
- Upload validation checks required columns, duplicate keys, numeric validity, finite/nonnegative values, integer quantities, and one invoice per order.
- No CORS policy, rate limiting, deployment TLS configuration, structured monitoring, or external secret manager was found in the repository. Absence in this checkout does not prove that infrastructure-level controls are absent elsewhere.
- `.env` exists and is ignored by Git; its contents were intentionally not opened. The audit does not verify whether it contains secrets or whether runtime secrets are configured correctly.
- No certificate, compliance, penetration-test, or production-security claim is made.

## Unverified assumptions

- No live provider call was made, so current Gemini credentials, model availability, quotas, response quality, and real tool-calling behavior are unverified.
- The existing SQLite DB was opened read-only for schema and aggregate status/provenance counts only; no row values or identities were retrieved, and no writes were made. Backups were not opened.
- No browser/server deployment was started, so network exposure, proxy limits, TLS, and actual dashboard/API connectivity are unverified.
- No deployment manifests or CI files were found among tracked files, so infrastructure-level protections and CI execution cannot be assessed.
- Input data in a future real deployment may differ from the repository’s synthetic/demo fixtures.

## Recommended tests

1. Configure and test aggregate request-body, multipart field-count, and temporary-storage limits before parsing untrusted uploads.
2. Test empty/invalid encodings, very wide/long CSVs, and parser resource limits.
3. Test every role against every workflow and chat/proposal tool, including any future third-person execution policy.
4. Test concurrent requests with different uploaded datasets and actors.
5. Test legacy SQLite migration and concurrent conditional transitions against temporary DB files; define a documented reconciliation process for pending actions without creation provenance.
6. Add dashboard-level mocked API and upload-flow tests.
7. Add controlled model contract evaluations, including prompt-injection examples and grounded-answer criteria; do not use production data.
