
"""Trusted per-request identity context for agent tools.

A trusted API or authentication middleware must set the actor.
The language model must never supply identity or organization claims.
"""

from contextvars import ContextVar, Token

from src.workflows.authorization import Actor, AuthorizationError


_current_actor: ContextVar[Actor | None] = ContextVar(
    "current_business_operations_actor",
    default=None,
)


def set_current_actor(actor: Actor) -> Token:
    """Set an authenticated actor for the current request context."""
    if not isinstance(actor, Actor):
        raise TypeError("A trusted Actor instance is required.")

    if not actor.user_id.strip() or not actor.organization_id.strip():
        raise AuthorizationError(
            "Authenticated user and organization are required."
        )

    return _current_actor.set(actor)


def reset_current_actor(token: Token) -> None:
    """Restore the previous request identity after handling a request."""
    _current_actor.reset(token)


def get_current_actor() -> Actor:
    """Return the trusted actor or reject unauthenticated access."""
    actor = _current_actor.get()

    if actor is None:
        raise AuthorizationError(
            "No authenticated actor is available for this request."
        )

    return actor
