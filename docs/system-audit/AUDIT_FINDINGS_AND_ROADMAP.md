# Audit Findings and Roadmap

**Audit date:** 2026-10-15

**Scope:** Repository code and tests in the current working tree, including the focused remediation described below. The existing SQLite database was queried read-only for schema and aggregate status/provenance counts only. No record values or identities were retrieved, no database writes were made, and no live external service was used.

## Executive summary

The repository has a useful end-to-end prototype: deterministic reconciliation, validated CSV uploads, a conversational agent, role-gated workflow actions, SQLite persistence, and a focused test suite. The original baseline passed **58 tests**; the final post-remediation suite passed **73 tests** with **6 dependency/framework warnings**.

The verified remediation makes inventory threshold reporting consistent, bounds per-file upload reads, and prevents an authenticated proposer from approving their own action. Remaining concerns include the absence of an aggregate request-body/temporary-storage limit, development-only bearer-token configuration, and pending legacy actions whose proposer cannot be verified from creation events. There are no P0 findings based on the inspected evidence. No live supplier, accounting, ERP, or payment operation exists.

## Contents

- [Verified strengths](#verified-strengths)
- [Technical debt and functional gaps](#technical-debt-and-functional-gaps)
- [Prioritized recommendations](#prioritized-recommendations)
- [Practical roadmap](#practical-roadmap)
- [Audit limitations](#audit-limitations)
- [Detailed evidence](#links-to-detailed-evidence)

## Verified strengths

- Reconciliation and prioritization are deterministic Python code, separate from model-generated prose.
- The agent has explicit instructions to use tool results as facts, avoid inventing records or causes, and distinguish interpretations/recommendations.
- CSV input is schema-checked and validated for several common errors.
- Uploaded business frames and actor identity are request-scoped and reset in a `finally` block.
- Workflow transitions require permissions and expected source states, and use organization-scoped SQL.
- Successful create/approve/execute transitions record actor and timestamp events; approval verifies a distinct proposer.
- Tests isolate SQLite state and exercise business logic, bounded upload handling, API authentication, workflow lifecycle, tool context, and fallback handling.
- Simulated execution is explicitly distinguished from placing a real purchase.

## Technical debt and functional gaps

- Multipart parsing still occurs before the handler's per-file limit check and may spool data to temporary storage; there is no aggregate request-body or temporary-storage cap.
- API authentication uses a process environment token registry described in source as development bootstrap.
- The administrator role receives every permission, but the workflow rejects approval by the same actor who proposed the action. Execution is not required to be a third distinct identity.
- Pending legacy actions without exactly one verifiable `ACTION_CREATED` actor remain unapprovable until manually reconciled.
- No reject/cancel/expiry/error-recovery states, real external execution, or idempotency key are implemented.
- SQLite schema has no declared action-event FK or append-only enforcement. Migration is inline and not versioned.
- Chat sessions are in memory. No backup/retention policy is implemented.
- The report assumes one invoice per order; uploads enforce this, but reconciliation helpers can also be called with arbitrary frames.
- No business-system connector, CI workflow, deployment manifest, README, or formal operator documentation was found in the tracked file listing.
- Dashboard does not provide action approval/execution screens.
- Prompt instructions are present but no explicit prompt-injection defense or model evaluation harness was found.

## Prioritized recommendations

### P0 — Critical safety or correctness issues

**None identified from the inspected code.** There is no production deployment or live external side effect in the reviewed implementation to support a critical-severity conclusion. This is not a claim that the system is formally secure.

### P1 — Required before a controlled pilot

1. **Set aggregate upload controls.** Configure request-body, multipart field-count, and temporary-storage limits at the server/proxy layer; the API's bounded per-file reads do not protect those parser-level resources.
2. **Replace or tightly constrain development authentication.** Use an identity provider or a documented local-only deployment boundary, and define token issuance, rotation, revocation, and secret storage.
3. **Reconcile unverified legacy proposals.** Establish an auditable process to identify proposers for pending actions that lack exactly one creation event; do not infer identities or bypass the fail-closed approval check.
4. **Explicitly label all workflow execution as simulated in user-facing and operator-facing interfaces.** Current API response does so; do not imply supplier orders or stock updates occur.
5. **Establish a data-handling plan for pilot CSVs.** Confirm permitted data, upload limits, retention/deletion, access, logs, and test fixtures before using real business information.

### P2 — Important before production

1. Move workflow persistence from local SQLite to a supported managed service if multi-instance/high availability is required; add schema migration versioning, backup/restore, retention, and access monitoring.
2. Add database-enforced referential integrity and a tamper-evident/externally retained audit design appropriate to business risk.
3. Add rate limiting, TLS/ingress configuration, structured logs, request correlation, metrics, alerting, and operational health checks.
4. Define currency/rounding policy and handle split/multiple invoices, payment evidence, tax, freight, and other supported source fields explicitly.
5. Add robust failure, rejection, cancellation, retry, duplicate request, idempotency, and reconciliation semantics before enabling external operations.
6. Add integration and UI tests, concurrency tests, adversarial upload tests, and controlled model grounding/prompt-injection evaluations.
7. Pin and document supported Python versions; validate dependency maintenance and establish CI gates.

### P3 — Future enhancements

1. Add connectors to accounting, ERP, inventory, order-management, HR, or supplier systems only after selecting authoritative sources and defining data contracts.
2. Add configurable business policies and thresholds, with approval and audit history for policy changes.
3. Add durable, privacy-governed conversation state if business users require continuity.
4. Add dashboards for action review, decision history, and operational trends.
5. Add demand forecasting or prioritization only when suitable verified data and validation criteria exist.

## Practical roadmap

### Immediate next steps

- Configure aggregate upload and temporary-storage limits.
- Document local-only authentication and protect the demo environment.
- Reconcile pending legacy actions without verified proposer provenance.
- Keep the existing demonstration data clearly labeled and avoid presenting it as customer output.

### Pilot readiness

- Use only approved non-production or synthetic data until privacy/retention controls are reviewed.
- Configure an identity provider or a narrowly scoped local pilot authentication model.
- Define who may propose, approve, and execute, and make simulation status conspicuous.
- Confirm that logs, temporary upload handling, and database storage meet the pilot’s data-handling expectations.
- Run tests and a controlled acceptance checklist against the selected sample workflow.

### Production readiness

- Select deployment topology, managed persistence, secrets, TLS, monitoring, backup, incident response, and retention controls.
- Define business rule ownership and edge cases (invoice multiplicity, currency, tax, credits, returns, inventory reservation).
- Design and test idempotent, observable adapters for each intended external side effect.
- Establish CI, dependency update/security processes, test gates, model evaluation, and release rollback.
- Conduct threat modeling and independent security review before exposing the API externally.

### Longer-term integrations and scalability

- Introduce source-specific adapters and canonical data contracts for chosen finance/ERP/order/inventory platforms.
- Reconcile updates and external outcomes back into verified source records.
- Evaluate durable sessions and scalable storage only where requirements justify them.
- Measure latency, throughput, quality, and operational benefit in a controlled pilot before making quantitative claims.

## Audit limitations

- Existing SQLite data was opened read-only for schema and aggregate status/provenance counts only; no record values or identities were retrieved and no writes were made. Backups were not opened.
- `.env` was intentionally not read. The audit reports configuration variable names only.
- No external model call, browser test, production request, or infrastructure inspection was performed.
- No CI workflow/deployment files were present in the tracked-file listing.
- The current checkout had pre-existing uncommitted changes. They were preserved; remediation edits were limited to directly related code, tests, and audit documentation. Findings describe the verified working tree.

## Links to detailed evidence

- [System overview](SYSTEM_OVERVIEW.md)
- [Architecture and data flow](ARCHITECTURE_AND_DATA_FLOW.md)
- [Business workflows](BUSINESS_WORKFLOWS.md)
- [API and data model](API_AND_DATA_MODEL.md)
- [Testing and security audit](TESTING_AND_SECURITY_AUDIT.md)
- [Developer and operator guide](DEVELOPER_AND_OPERATOR_GUIDE.md)
- [Portfolio case study](PORTFOLIO_TECHNICAL_CASE_STUDY.md)
