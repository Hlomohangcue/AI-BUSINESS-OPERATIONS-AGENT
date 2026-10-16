
from copy import deepcopy
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

from src.workflows.authorization import (
    Actor,
    Permission,
    require_permission,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "workflow_actions.db"
LEGACY_ORGANIZATION_ID = "default"


def _get_db_path() -> Path:
    """Return the configured workflow database path."""
    configured_path = os.getenv("WORKFLOW_DB_PATH")

    if configured_path:
        return Path(configured_path).expanduser().resolve()

    return DEFAULT_DB_PATH


def _connect() -> sqlite3.Connection:
    """Open the database and safely migrate it for tenant isolation."""
    db_path = _get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(db_path, timeout=10)
    connection.row_factory = sqlite3.Row

    try:
        connection.execute("PRAGMA foreign_keys = ON")

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_actions (
                action_id TEXT PRIMARY KEY,
                action TEXT NOT NULL,
                sku TEXT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL CHECK (
                    status IN (
                        'PENDING_APPROVAL',
                        'APPROVED',
                        'EXECUTED'
                    )
                ),
                created_at TEXT NOT NULL,
                approved_by TEXT,
                approved_at TEXT,
                executed_at TEXT,
                organization_id TEXT NOT NULL DEFAULT 'default'
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_action_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_id TEXT NOT NULL,
                event_type TEXT NOT NULL CHECK (
                    event_type IN (
                        'ACTION_CREATED',
                        'ACTION_APPROVED',
                        'ACTION_EXECUTED'
                    )
                ),
                actor TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                organization_id TEXT NOT NULL DEFAULT 'default'
            )
            """
        )

        # Add the tenant column to existing databases without deleting data.
        action_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(workflow_actions)"
            ).fetchall()
        }

        if "organization_id" not in action_columns:
            connection.execute(
                """
                ALTER TABLE workflow_actions
                ADD COLUMN organization_id TEXT NOT NULL DEFAULT 'default'
                """
            )

        event_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(workflow_action_events)"
            ).fetchall()
        }

        if "organization_id" not in event_columns:
            connection.execute(
                """
                ALTER TABLE workflow_action_events
                ADD COLUMN organization_id TEXT NOT NULL DEFAULT 'default'
                """
            )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_actions_organization_status
            ON workflow_actions (organization_id, status)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_events_organization_action
            ON workflow_action_events (organization_id, action_id, event_id)
            """
        )

        connection.commit()
        return connection

    except Exception:
        connection.rollback()
        connection.close()
        raise


def _get_action(action_id: str, actor: Actor) -> dict | None:
    """Retrieve an action only within the authorized actor's organization."""
    require_permission(actor, Permission.VIEW_OPERATIONS)

    with _connect() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM workflow_actions
            WHERE action_id = ?
              AND organization_id = ?
            """,
            (action_id, actor.organization_id),
        ).fetchone()

    return dict(row) if row else None


def _record_event(
    connection: sqlite3.Connection,
    action_id: str,
    organization_id: str,
    event_type: str,
    actor: str,
    occurred_at: str,
) -> None:
    """Record an event only when its action belongs to the same organization."""
    cursor = connection.execute(
        """
        INSERT INTO workflow_action_events (
            action_id,
            event_type,
            actor,
            occurred_at,
            organization_id
        )
        SELECT action_id, ?, ?, ?, organization_id
        FROM workflow_actions
        WHERE action_id = ?
          AND organization_id = ?
        """,
        (
            event_type,
            actor,
            occurred_at,
            action_id,
            organization_id,
        ),
    )

    if cursor.rowcount != 1:
        raise RuntimeError(
            "Audit event was not recorded: action organization mismatch."
        )


def get_workflow_action_events(
    action_id: str,
    actor: Actor,
) -> list[dict]:
    """Return audit history only for actions in the actor's organization."""
    require_permission(actor, Permission.VIEW_OPERATIONS)

    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT
                event_id,
                action_id,
                event_type,
                actor,
                occurred_at,
                organization_id
            FROM workflow_action_events
            WHERE action_id = ?
              AND organization_id = ?
              AND EXISTS (
                  SELECT 1
                  FROM workflow_actions
                  WHERE workflow_actions.action_id = ?
                    AND workflow_actions.organization_id = ?
              )
            ORDER BY event_id
            """,
            (
                action_id,
                actor.organization_id,
                action_id,
                actor.organization_id,
            ),
        ).fetchall()

    return [dict(row) for row in rows]


def create_replenishment_request(
    sku: str,
    reason: str,
    actor: Actor,
) -> dict:
    """Create an authorized replenishment request for the actor's organization."""
    require_permission(actor, Permission.PROPOSE_ACTION)

    sku = sku.strip()
    reason = reason.strip()

    if not sku or not reason:
        raise ValueError("SKU and reason are required.")

    action = {
        "action_id": f"ACT-{uuid4().hex[:8].upper()}",
        "action": "REPLENISHMENT_REQUEST",
        "sku": sku,
        "reason": reason,
        "status": "PENDING_APPROVAL",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "approved_by": None,
        "approved_at": None,
        "executed_at": None,
        "organization_id": actor.organization_id,
    }

    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO workflow_actions (
                action_id,
                action,
                sku,
                reason,
                status,
                created_at,
                approved_by,
                approved_at,
                executed_at,
                organization_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                action["action_id"],
                action["action"],
                action["sku"],
                action["reason"],
                action["status"],
                action["created_at"],
                None,
                None,
                None,
                actor.organization_id,
            ),
        )

        _record_event(
            connection,
            action["action_id"],
            actor.organization_id,
            "ACTION_CREATED",
            actor.user_id,
            action["created_at"],
        )

    return deepcopy(action)


def propose_replenishment_request(
    sku: str,
    reason: str,
    actor: Actor,
) -> dict:
    """Create an authorized proposal that requires human approval."""
    return create_replenishment_request(
        sku=sku,
        reason=reason,
        actor=actor,
    )


def approve_workflow_action(
    action_id: str,
    actor: Actor,
) -> dict:
    """Approve a pending action proposed by a different verified actor."""
    require_permission(actor, Permission.APPROVE_ACTION)

    approved_at = datetime.now(timezone.utc).isoformat()

    with _connect() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM workflow_actions
            WHERE action_id = ?
              AND organization_id = ?
            """,
            (action_id, actor.organization_id),
        ).fetchone()

        if row is None:
            return {
                "found": False,
                "action_id": action_id,
                "message": f"Workflow action {action_id} not found.",
            }

        result = dict(row)
        result["found"] = True

        if row["status"] != "PENDING_APPROVAL":
            result["message"] = "Only pending actions can be approved."
            return result

        provenance = connection.execute(
            """
            SELECT COUNT(*) AS event_count, MIN(actor) AS proposer
            FROM workflow_action_events
            WHERE action_id = ?
              AND organization_id = ?
              AND event_type = 'ACTION_CREATED'
            """,
            (action_id, actor.organization_id),
        ).fetchone()

        if (
            provenance["event_count"] != 1
            or not isinstance(provenance["proposer"], str)
            or not provenance["proposer"].strip()
        ):
            result["message"] = (
                "The proposer cannot be verified for this action."
            )
            return result

        if provenance["proposer"] == actor.user_id:
            result["message"] = (
                "The proposer cannot approve their own action."
            )
            return result

        cursor = connection.execute(
            """
            UPDATE workflow_actions
            SET status = 'APPROVED',
                approved_by = ?,
                approved_at = ?
            WHERE action_id = ?
              AND organization_id = ?
              AND status = 'PENDING_APPROVAL'
            """,
            (
                actor.user_id,
                approved_at,
                action_id,
                actor.organization_id,
            ),
        )

        if cursor.rowcount == 1:
            _record_event(
                connection,
                action_id,
                actor.organization_id,
                "ACTION_APPROVED",
                actor.user_id,
                approved_at,
            )

            row = connection.execute(
                """
                SELECT *
                FROM workflow_actions
                WHERE action_id = ?
                  AND organization_id = ?
                """,
                (action_id, actor.organization_id),
            ).fetchone()

            return dict(row)

        # A concurrent transition may have changed the action after the read.
        row = connection.execute(
            """
            SELECT *
            FROM workflow_actions
            WHERE action_id = ?
              AND organization_id = ?
            """,
            (action_id, actor.organization_id),
        ).fetchone()

        if row is None:
            return {
                "found": False,
                "action_id": action_id,
                "message": f"Workflow action {action_id} not found.",
            }

    result = dict(row)
    result["found"] = True
    result["message"] = "Only pending actions can be approved."
    return result


def execute_workflow_action(
    action_id: str,
    actor: Actor,
) -> dict:
    """Simulate execution only for an approved action in the actor's organization."""
    require_permission(actor, Permission.EXECUTE_ACTION)

    executed_at = datetime.now(timezone.utc).isoformat()

    with _connect() as connection:
        cursor = connection.execute(
            """
            UPDATE workflow_actions
            SET status = 'EXECUTED',
                executed_at = ?
            WHERE action_id = ?
              AND organization_id = ?
              AND status = 'APPROVED'
            """,
            (
                executed_at,
                action_id,
                actor.organization_id,
            ),
        )

        if cursor.rowcount == 1:
            _record_event(
                connection,
                action_id,
                actor.organization_id,
                "ACTION_EXECUTED",
                actor.user_id,
                executed_at,
            )

            row = connection.execute(
                """
                SELECT *
                FROM workflow_actions
                WHERE action_id = ?
                  AND organization_id = ?
                """,
                (action_id, actor.organization_id),
            ).fetchone()

            return dict(row)

        # Do not reveal whether an action exists in another organization.
        row = connection.execute(
            """
            SELECT *
            FROM workflow_actions
            WHERE action_id = ?
              AND organization_id = ?
            """,
            (action_id, actor.organization_id),
        ).fetchone()

    if row is None:
        return {
            "found": False,
            "action_id": action_id,
            "message": f"Workflow action {action_id} not found.",
        }

    result = dict(row)
    result["found"] = True
    result["message"] = "Only approved actions can be executed."
    return result
