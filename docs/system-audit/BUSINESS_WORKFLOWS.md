# Business Workflows

**Scope note:** Examples in this document are synthetic and illustrative only. No example below is a live business record. The application source includes labeled demonstration CSVs; their presence is not evidence of customer deployment.

## Contents

- [1. Operations reporting](#1-operations-reporting)
- [2. Order investigation](#2-order-investigation)
- [3. Invoice reconciliation](#3-invoice-reconciliation)
- [4. Inventory monitoring](#4-inventory-monitoring)
- [5. Replenishment proposals](#5-replenishment-proposals)
- [6. Approval and execution](#6-approval-and-execution)
- [7. Audit events](#7-audit-events)
- [Manual steps and limitations](#manual-steps-and-limitations)

## 1. Operations reporting

**Code path:** [`build_operations_report()`](../../src/reconciliation/report.py), reconciliation helpers in [`engine.py`](../../src/reconciliation/engine.py), priorities in [`business_rules.py`](../../src/reconciliation/business_rules.py).

1. If no data frames are provided, the engine reads `orders.csv`, `invoices.csv`, and `inventory.csv` from `src/data/`.
2. Otherwise, the report requires all three data frames; partial input raises `ValueError`.
3. Orders are left-joined to invoices by `order_id`; inventory is checked against the configured reorder level; invoices referring to absent orders are separately collected as orphans.
4. Summary counts and JSON-safe exception record lists are returned.

Report summary keys are `orders_processed`, `invoices_processed`, `inventory_records`, `matched_orders`, `financial_exceptions`, `orphan_invoices`, and `inventory_exceptions`. Missing pandas NaN values are converted to JSON `null` in report records.

The Streamlit dashboard supports demonstration data when no files are uploaded, or requires all three uploads together. The dashboard generates the displayed report locally. Its agent chat separately sends the prompt to the API; on a complete upload it sends the three CSV files as multipart data so agent tools can use them within that API request.

## 2. Order investigation

The `investigate_order(order_id)` agent tool calls `get_order_exception_details()`. That lookup returns `found`, order fields (customer, SKU, quantity, unit price, expected amount), invoice fields (ID, amount, recorded status), and reconciliation status/difference. Unknown IDs return `found: false`.

The deterministic engine derives `expected_amount = quantity * unit_price`. It labels an order `MISSING_INVOICE` when the left join has no invoice; otherwise, it labels `AMOUNT_MISMATCH` when the absolute difference exceeds `0.01`, and `MATCHED` otherwise.

**Synthetic example:** Order quantity `2`, unit price `$10.00`, and matching invoice amount `$25.00` yields expected amount `$20.00` and a `$5.00` difference. It does not identify the cause of the discrepancy.

## 3. Invoice reconciliation

Invoice rows are matched by `order_id`. The report identifies:

- **Amount mismatch:** an order has an invoice and the difference is greater than one cent in absolute value.
- **Missing invoice:** an order row has no matching invoice in the supplied order/invoice datasets.
- **Orphan invoice:** an invoice references an order ID absent from the supplied order dataset.

The upload validator enforces unique invoice IDs and at most one invoice per order. The invoice schema has only `invoice_id`, `order_id`, `invoice_amount`, and `status`; there is no payment ledger, tax, shipping, discount, or settlement evidence. Therefore, a status such as “Paid” is invoice metadata only and does not prove a bank payment.

**Synthetic example:** If an invoice references `SYN-ORDER-404` but no corresponding order exists in the uploaded orders file, it is classified as an orphan invoice. The system cannot determine whether the cause is an export omission, data-entry issue, or another event.

## 4. Inventory monitoring

`find_low_stock_items()` selects rows where `stock_quantity <= reorder_level`; the entity lookup now uses the same inclusive threshold for `LOW_STOCK`. Zero stock remains `OUT_OF_STOCK` in the entity lookup and `CRITICAL` in the report. The `below_reorder_level` detail remains a strict `<` comparison, so an item exactly at the threshold is low stock but is not strictly below the configured level. Regression tests cover below, equal, above, and zero-stock cases.

The report includes recorded `unit_cost` but does not compute purchase quantities, total replenishment cost, demand forecasts, supplier lead times, or safety stock. No stock mutation or purchase order is performed.

**Synthetic example:** Stock `4`, configured reorder level `5` is reported as below threshold. The application has no demand or supplier data to quantify a stockout date.

## 5. Replenishment proposals

The agent tool `propose_inventory_replenishment(sku, reason)` obtains the trusted actor from request context and calls `propose_replenishment_request()`. The API route `POST /workflow/replenishment` also accepts `sku` and `reason`. The workflow checks the actor has `PROPOSE_ACTION`, strips whitespace, requires both strings, generates an action ID, records `PENDING_APPROVAL`, and writes an `ACTION_CREATED` event.

No inventory quantity, supplier, purchase amount, delivery date, or purchase-order reference is included in the proposal schema. The proposal is a local request record, not a supplier order.

## 6. Approval and execution

An actor with `APPROVE_ACTION` may transition an action from `PENDING_APPROVAL` to `APPROVED` only when exactly one non-empty `ACTION_CREATED` event identifies a different proposer. An unverified proposer and a proposer attempting self-approval leave the action pending and return a conflict. An actor with `EXECUTE_ACTION` may transition it from `APPROVED` to `EXECUTED`; execution identity is not required to differ from either the proposer or approver. Transitions use conditional SQL updates, scoped to the actor’s organization, and add a corresponding event only when the update succeeds.

`POST /workflow/actions/{action_id}/execute` explicitly responds that execution is simulated and no external purchase was placed. There is no rejection or cancellation operation. An administrator has every permission in the static role table, but cannot approve their own proposal. Existing pending actions without exactly one verifiable creation event are not automatically attributed and cannot be approved until separately reconciled.

## 7. Audit events

For successful lifecycle operations, event types are:

| Operation | Event type | Stored actor |
|---|---|---|
| Proposal creation | `ACTION_CREATED` | Authenticated proposer `user_id` |
| Approval | `ACTION_APPROVED` | Approver `user_id` |
| Simulated execution | `ACTION_EXECUTED` | Executor `user_id` |

Each event stores an integer ID, action ID, event type, actor, UTC ISO timestamp, and organization ID. Reads are organization-scoped and ordered by event ID. Failed transitions do not produce success events; tests cover that behavior. The API has no event update/delete route, but the database schema does not enforce immutability against direct database access.

## Manual steps and limitations

- A person must prepare correctly structured CSVs; no connector or scheduled import is implemented.
- A person must review mismatches and decide business causes using records not included in the app.
- The current action process requires a separate API caller for approval/execution; no dashboard approval screen is present.
- “Executed” records only the local simulated transition.
- Upload support rejects multiple invoices for one order rather than aggregating them.
- Historical pending actions without verifiable creation events require manual reconciliation before approval.
- Currency calculations use Python/Pandas numeric values; no decimal currency representation or currency-code handling is present.
- No workflow for approval rejection, cancellation, expiry, recovery, supplier response, or delivery confirmation was found.
