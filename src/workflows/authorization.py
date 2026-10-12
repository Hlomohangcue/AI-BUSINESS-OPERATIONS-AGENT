
"""Centralized role-based authorization for business workflows."""

from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    VIEWER = "viewer"
    OPERATOR = "operator"
    APPROVER = "approver"
    ADMINISTRATOR = "administrator"


class Permission(StrEnum):
    VIEW_OPERATIONS = "view_operations"
    PROPOSE_ACTION = "propose_action"
    APPROVE_ACTION = "approve_action"
    EXECUTE_ACTION = "execute_action"
    MANAGE_USERS = "manage_users"


class AuthorizationError(PermissionError):
    """Raised when an actor lacks a required permission."""


@dataclass(frozen=True, slots=True)
class Actor:
    """Identity and organization context supplied by a trusted backend."""

    user_id: str
    organization_id: str
    role: Role


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.VIEWER: frozenset({
        Permission.VIEW_OPERATIONS,
    }),
    Role.OPERATOR: frozenset({
        Permission.VIEW_OPERATIONS,
        Permission.PROPOSE_ACTION,
    }),
    Role.APPROVER: frozenset({
        Permission.VIEW_OPERATIONS,
        Permission.APPROVE_ACTION,
        Permission.EXECUTE_ACTION,
    }),
    Role.ADMINISTRATOR: frozenset(Permission),
}


def require_permission(
    actor: Actor,
    permission: Permission,
) -> None:
    """Reject missing identity or insufficient role permissions."""

    if not actor.user_id.strip():
        raise AuthorizationError("Authenticated user identity is required.")

    if not actor.organization_id.strip():
        raise AuthorizationError("Organization context is required.")

    if permission not in ROLE_PERMISSIONS.get(actor.role, frozenset()):
        raise AuthorizationError(
            f"Role '{actor.role.value}' cannot perform "
            f"'{permission.value}'."
        )
