# AI Business Operations Agent

## An AI-assisted reconciliation and workflow prototype by Slimes.Hustlers AI Solutions

### Executive summary

The AI Business Operations Agent is a Python prototype for reviewing order, invoice, and inventory CSV data. It uses deterministic rules to compute reconciliation outcomes and an ADK/Gemini agent to explain tool results in business language. A separate authenticated API workflow can create replenishment proposals, record approvals, and mark a proposal as simulated-executed in SQLite.

This project demonstrates implementation patterns for AI-assisted business workflows. Repository sample data and deterministic test fixtures demonstrate those patterns; they do not establish customer use, production deployment, or measured financial impact.

## Contents

- [Business problem](#business-problem)
- [Proposed technical solution](#proposed-technical-solution)
- [Architecture and design decisions](#architecture-and-design-decisions)
- [Deterministic business logic versus LLM reasoning](#deterministic-business-logic-versus-llm-reasoning)
- [Reconciliation and exception detection](#reconciliation-and-exception-detection-workflows)
- [Approval controls and auditability](#approval-controls-and-auditability)
- [Data persistence](#data-persistence)
- [Testing and quality assurance](#testing-and-quality-assurance)
- [Security considerations](#security-considerations)
- [Challenges and trade-offs](#challenges-and-engineering-trade-offs)
- [Verified outcomes](#verified-outcomes)
- [Limitations and roadmap](#current-limitations-and-roadmap)
- [Skills demonstrated](#skills-demonstrated)
- [Interview talking points](#interview-talking-points)

## Business problem

Small operations teams may need to compare data exported from separate systems and quickly identify invoice mismatches, orders with no invoice in the supplied dataset, orphan invoice references, and inventory at or below a configured reorder level. A conversational interface can make the deterministic findings easier to inspect, but generated explanation must not replace the source calculations or human decision-making.

## Proposed technical solution

The implementation separates data checks from language generation:

1. Pandas-based code loads sample CSVs or validates a complete uploaded set.
2. Deterministic rules reconcile order and invoice values and identify inventory exceptions.
3. Google ADK exposes report and entity-investigation functions as agent tools.
4. The agent receives instructions to ground claims in tool output and distinguish verified facts, interpretation, and recommendations.
5. A role-checked FastAPI workflow records proposals, approvals, simulated execution, and event history in SQLite.

## Architecture and design decisions

- **Python/Pandas:** structured CSV normalization and tabular calculations.
- **FastAPI:** HTTP interface for chat and workflow actions.
- **Streamlit:** local reporting and conversational dashboard.
- **Google ADK and Gemini:** tool-calling agent and natural-language response generation.
- **SQLite:** local workflow state and event rows.
- **ContextVars:** request-local authenticated actor and optional uploaded datasets, reset in `finally` after the agent run.
- **Conditional state updates:** approval and execution only succeed from allowed source states.
- **Role-based access:** viewer, operator, approver, and administrator roles have distinct permission sets, with administrator granted all permissions.

The model configuration uses a primary Gemini model with a fallback implementation. The fallback is attempted only when the primary fails before yielding output; it deliberately does not restart after partial output to avoid duplicate responses.

## Deterministic business logic versus LLM reasoning

The following are deterministic in source:

- Expected order value is `quantity × unit_price`.
- Orders and invoices are matched by `order_id`.
- Amount mismatch is based on absolute difference greater than `$0.01`.
- Missing invoices and orphan invoices are identified from record relationships.
- Inventory report rows are selected at or below the configured reorder level.
- Fixed priorities and recommended action strings are assigned in `business_rules.py`.
- CSV validation rejects missing required values, invalid numeric fields, duplicates, negative values, and multiple invoices referencing one order.

The LLM chooses tools and produces explanations. Its system instruction says not to invent business facts, to use tool output as the source of truth, and to label interpretation/recommendations. Those are useful prompt-level safeguards but do not make generated text deterministic or guarantee correctness.

## Reconciliation and exception-detection workflows

The report returns counts and separate lists for financial exceptions, orphan invoices, and inventory exceptions. Entity investigation tools return a structured `found` result, verified record fields, and reconciliation status. The source schema does not include payment transaction data, tax, freight, discounts, demand forecasts, or supplier lead time, so those topics cannot be verified by the implemented logic.

The CSV upload path uses all three datasets together. Request-scoped datasets are deep-copied before being placed in a ContextVar and cleared after the agent call. The current validator supports no more than one invoice per order.

## Approval controls and auditability

The lifecycle is `PENDING_APPROVAL → APPROVED → EXECUTED`. A proposal creates an action row and `ACTION_CREATED` event. Successful approval and execution each write one matching event in the same SQLite connection context. Invalid or repeated transitions do not create a success event. Organization IDs scope action reads and updates.

Execution is explicitly simulated. There is no live supplier purchase or stock change. The static permission model does not require a different person to approve an administrator’s own proposal. The event table has no database-enforced append-only property.

## Data persistence

Business CSV uploads are held for a request/session and are not persisted by the upload handler. The workflow database stores action details, status, timestamps, actor identifiers, and organization IDs. Chat sessions use an ADK in-memory service and do not survive a process restart. No data backup, retention, or recovery process is implemented in this repository.

## Testing and quality assurance

The test suite covers deterministic reconciliation, CSV validation, agent tools using uploaded datasets, API authentication/authorization, lifecycle transitions, event provenance, bounded upload handling, and Gemini fallback behavior with fakes. The original baseline passed **58 tests**; after targeted remediation, the final suite passed **73 tests** with six dependency/framework warnings. Tests isolate workflow storage through `tmp_path`. No live model call or browser UI test was performed.

## Security considerations

The implementation parameterizes SQL values, validates uploaded business CSV structure, maps bearer tokens to configured server-side actors, checks permissions, scopes workflow rows to organizations, and resets request context. It also includes limitations relevant to real deployment: development token-registry authentication, no explicit prompt-injection defense, upload size checked after bytes are read, admin actions are not separated, and local SQLite audit events are not tamper-proof.

## Challenges and engineering trade-offs

- CSV provides a low-friction demonstration format but is not a transactional source of truth.
- The one-invoice-per-order constraint simplifies matching but does not cover split billing.
- A fixed one-cent threshold and binary inventory threshold keep logic explainable but omit richer accounting/inventory policies.
- In-memory model sessions simplify local development but are ephemeral.
- SQLite simplifies a prototype but does not establish a distributed persistence design.
- A human approval state provides a control boundary, while simulated execution avoids external side effects in the current prototype.

## Verified outcomes

- The deterministic report and tool functions are implemented and covered by tests.
- The API and role-guarded workflow lifecycle are implemented and covered by tests.
- The final isolated test run passed all 73 tests.
- The codebase includes a dashboard, API, agent, CSV validation, sample data generator, and local workflow persistence.

No live customer, production rollout, savings figure, transaction volume, latency target, or external integration is claimed.

## Current limitations and roadmap

Authentication remains a development bootstrap. CSV reads are bounded per file and parsed form resources are closed, but there is no aggregate request-body or temporary-storage limit. Proposers cannot approve their own actions; pending legacy actions without verified creation provenance require manual reconciliation. Rejection/cancellation and actual external execution are absent, and execution is not required to use a third distinct actor. There is no CI workflow or deployment configuration in the tracked repository listing.

Future work could address those remaining issues, add managed identity/database/monitoring, test adversarial inputs, and introduce adapters for accounting, ERP, HR, or order systems. Those are future integration opportunities, not current capabilities.

## Skills demonstrated

- Python application design and API development.
- CSV validation, normalization, and deterministic reconciliation.
- Google ADK tool design and Gemini model fallback.
- Role/tenant-aware authorization.
- SQLite lifecycle state and audit-event persistence.
- Test design across business logic, API, workflow state, upload handling, and model fallback.
- Human-in-the-loop automation design and explicit safety boundaries.

## Interview talking points

1. Why were reconciliation calculations kept deterministic and the LLM used for explanation?
2. How does request-scoped context prevent uploaded datasets or actors from leaking between requests?
3. What must change before simulated execution is connected to a supplier or ERP side effect?
4. What does an audit-event row prove, and what does it not prove about tamper resistance?
5. How would you test prompt injection and model grounding without using customer data?
6. How would you handle split invoices, currency/rounding policy, and authoritative source reconciliation?
