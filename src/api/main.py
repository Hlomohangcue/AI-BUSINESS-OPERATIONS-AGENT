
"""Authenticated API for business workflow operations.

Development bootstrap: bearer tokens are mapped to trusted actors
using server-side configuration. Replace this with an identity provider
before exposing the service publicly.
"""

import logging

logger = logging.getLogger(__name__)

import hmac
import json
import os
from typing import Annotated, Any

import io

import pandas as pd
from fastapi import Request
from pydantic import ValidationError
from starlette.datastructures import UploadFile

from src.agents.business_data_context import (
    set_current_business_data,
    reset_current_business_data,
)
from src.reconciliation.uploads import validate_business_csv

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from src.workflows.actions import (
    _get_action,
    approve_workflow_action,
    execute_workflow_action,
    get_workflow_action_events,
    propose_replenishment_request,
)
from src.workflows.authorization import (
    Actor,
    AuthorizationError,
    Role,
)

import hashlib

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from src.agents.business_operations_agent import root_agent
from src.agents.request_context import (
    set_current_actor,
    reset_current_actor,
)


app = FastAPI(
    title="AI Business Operations API",
    version="0.1.0",
    description="Authenticated workflow operations API.",
)

bearer_scheme = HTTPBearer(auto_error=False)


class ReplenishmentRequest(BaseModel):
    sku: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=2000)
    

class AgentChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)


MAX_CSV_UPLOAD_BYTES = 5 * 1024 * 1024


async def _read_csv_upload(upload: UploadFile, field_name: str) -> bytes:
    """Read at most one byte beyond the configured CSV upload limit."""
    if (
        upload.size is not None
        and upload.size > MAX_CSV_UPLOAD_BYTES
    ):
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"{field_name} exceeds the 5 MiB limit.",
        )

    raw = await upload.read(MAX_CSV_UPLOAD_BYTES + 1)

    if len(raw) > MAX_CSV_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"{field_name} exceeds the 5 MiB limit.",
        )

    if not raw:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} is empty.",
        )

    return raw


async def _parse_multipart_chat_request(
    request: Request,
) -> tuple[str, tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame] | None]:
    """Parse and close a multipart chat request, including uploaded CSVs."""
    try:
        form = await request.form()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The multipart request could not be read.",
        ) from None

    try:
        message_value = form.get("message")
        message = (
            message_value.strip()
            if isinstance(message_value, str)
            else ""
        )

        file_fields = {
            "orders_file": form.get("orders_file"),
            "invoices_file": form.get("invoices_file"),
            "inventory_file": form.get("inventory_file"),
        }
        supplied = {
            name: value
            for name, value in file_fields.items()
            if value is not None
        }

        if supplied and len(supplied) != 3:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Upload orders, invoices, and inventory CSV files "
                    "together, or upload none of them."
                ),
            )

        datasets = None

        if supplied:
            parsed_datasets = {}
            dataset_names = {
                "orders_file": "orders",
                "invoices_file": "invoices",
                "inventory_file": "inventory",
            }

            for field_name, dataset_name in dataset_names.items():
                upload = file_fields[field_name]

                if not isinstance(upload, UploadFile):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"{field_name} must be a CSV file.",
                    )

                if (
                    upload.filename
                    and not upload.filename.lower().endswith(".csv")
                ):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"{field_name} must have a .csv filename.",
                    )

                raw = await _read_csv_upload(upload, field_name)

                try:
                    dataframe = pd.read_csv(io.BytesIO(raw))
                    parsed_datasets[dataset_name] = validate_business_csv(
                        dataframe,
                        dataset_name,
                    )
                except (
                    ValueError,
                    UnicodeDecodeError,
                    pd.errors.ParserError,
                    pd.errors.EmptyDataError,
                ):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=(
                            f"{field_name} could not be parsed or failed "
                            "CSV validation."
                        ),
                    ) from None

            datasets = (
                parsed_datasets["orders"],
                parsed_datasets["invoices"],
                parsed_datasets["inventory"],
            )

        return message, datasets
    finally:
        await form.close()


# Local-development session storage. Conversations are lost on restart.
agent_session_service = InMemorySessionService()

agent_runner = Runner(
    app_name="business_operations_api",
    agent=root_agent,
    session_service=agent_session_service,
)


def get_authenticated_actor(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> Actor:
    """Resolve a bearer token to a server-configured identity."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer authentication is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    configured_tokens = os.getenv("BUSINESS_OPERATIONS_API_TOKENS_JSON")

    if not configured_tokens:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication has not been configured.",
        )

    try:
        token_registry: dict[str, dict[str, Any]] = json.loads(
            configured_tokens
        )
        if not isinstance(token_registry, dict):
            raise ValueError("Token registry must be a JSON object.")
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication configuration is invalid.",
        ) from None

    matched_identity = None

    # Compare against configured secrets without directly indexing by token.
    supplied_token = credentials.credentials
    for configured_token, identity in token_registry.items():
        if (
            isinstance(configured_token, str)
            and hmac.compare_digest(supplied_token, configured_token)
        ):
            matched_identity = identity
            break

    if not isinstance(matched_identity, dict):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = matched_identity["user_id"]
        organization_id = matched_identity["organization_id"]
        role = Role(matched_identity["role"])

        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("Invalid user identity.")
        if not isinstance(organization_id, str) or not organization_id.strip():
            raise ValueError("Invalid organization identity.")

        return Actor(
            user_id=user_id,
            organization_id=organization_id,
            role=role,
        )
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A configured API identity is invalid.",
        ) from None


AuthenticatedActor = Annotated[Actor, Depends(get_authenticated_actor)]


def _translate_authorization_error(error: AuthorizationError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=str(error),
    )


def _require_action(
    action_id: str,
    actor: Actor,
) -> dict:
    """Fetch an action within the caller's organization or return 404."""
    try:
        action = _get_action(action_id, actor)
    except AuthorizationError as error:
        raise _translate_authorization_error(error) from None

    if action is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow action not found.",
        )

    return action


@app.get("/health")
def health() -> dict[str, str]:
    """Basic process health check; does not expose business data."""
    return {"status": "ok"}


@app.post("/workflow/replenishment", status_code=status.HTTP_201_CREATED)
def create_replenishment(
    request: ReplenishmentRequest,
    actor: AuthenticatedActor,
) -> dict:
    """Create a proposal for the authenticated organization."""
    try:
        action = propose_replenishment_request(
            sku=request.sku.strip(),
            reason=request.reason.strip(),
            actor=actor,
        )
        return {
            "success": True,
            "action": action,
            "message": "Proposal created and awaiting human approval.",
        }
    except AuthorizationError as error:
        raise _translate_authorization_error(error) from None
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from None


@app.get("/workflow/actions/{action_id}")
def get_action(
    action_id: str,
    actor: AuthenticatedActor,
) -> dict:
    """Retrieve an action visible to the authenticated organization."""
    return _require_action(action_id, actor)


@app.get("/workflow/actions/{action_id}/events")
def get_action_events(
    action_id: str,
    actor: AuthenticatedActor,
) -> dict:
    """Retrieve audit events for an action in the caller's organization."""
    _require_action(action_id, actor)

    try:
        events = get_workflow_action_events(action_id, actor)
    except AuthorizationError as error:
        raise _translate_authorization_error(error) from None

    return {"action_id": action_id, "events": events}


@app.post("/workflow/actions/{action_id}/approve")
def approve_action(
    action_id: str,
    actor: AuthenticatedActor,
) -> dict:
    """Approve an action when the actor's role permits it."""
    _require_action(action_id, actor)

    try:
        result = approve_workflow_action(action_id, actor)
    except AuthorizationError as error:
        raise _translate_authorization_error(error) from None

    if not result.get("found", True):
        raise HTTPException(status_code=404, detail="Workflow action not found.")

    if result.get("status") != "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=result.get("message", "Action cannot be approved."),
        )

    return {"success": True, "action": result}


@app.post("/workflow/actions/{action_id}/execute")
def execute_action(
    action_id: str,
    actor: AuthenticatedActor,
) -> dict:
    """Execute an approved workflow action, subject to role authorization."""
    _require_action(action_id, actor)

    try:
        result = execute_workflow_action(action_id, actor)
    except AuthorizationError as error:
        raise _translate_authorization_error(error) from None

    if not result.get("found", True):
        raise HTTPException(status_code=404, detail="Workflow action not found.")

    if result.get("status") != "EXECUTED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=result.get("message", "Action cannot be executed."),
        )

    return {
        "success": True,
        "action": result,
        "note": "Execution is simulated; no external purchase was placed.",
    }



@app.post("/agent/chat")
async def agent_chat(
    request: Request,
    actor: AuthenticatedActor,
) -> dict:
    """Run the agent with optional request-scoped CSV datasets."""

    datasets = None
    content_type = request.headers.get("content-type", "").lower()

    # Preserve JSON requests while also accepting multipart CSV uploads.
    if content_type.startswith("application/json"):
        try:
            payload = await request.json()
            chat_request = AgentChatRequest.model_validate(payload)
        except (json.JSONDecodeError, ValidationError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Provide a valid JSON object containing a message.",
            ) from None

        message = chat_request.message.strip()

    elif content_type.startswith("multipart/form-data"):
        message, datasets = await _parse_multipart_chat_request(request)

    else:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Use application/json or multipart/form-data.",
        )

    if not message:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message cannot be empty.",
        )

    if len(message) > 10000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message must not exceed 10000 characters.",
        )

    # Derive ADK identifiers from the authenticated server-side identity.
    identity = f"{actor.organization_id}:{actor.user_id}"
    session_key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    adk_user_id = session_key
    adk_session_id = f"session-{session_key}"

    try:
        session = await agent_session_service.get_session(
            app_name="business_operations_api",
            user_id=adk_user_id,
            session_id=adk_session_id,
        )

        if session is None:
            await agent_session_service.create_session(
                app_name="business_operations_api",
                user_id=adk_user_id,
                session_id=adk_session_id,
            )

        content = types.Content(
            role="user",
            parts=[types.Part(text=message)],
        )

        response_text = []

        actor_token = set_current_actor(actor)
        dataset_token = None

        try:
            if datasets is not None:
                dataset_token = set_current_business_data(*datasets)

            async for event in agent_runner.run_async(
                user_id=adk_user_id,
                session_id=adk_session_id,
                new_message=content,
            ):
                if (
                    event.is_final_response()
                    and event.content
                    and event.content.parts
                ):
                    response_text.extend(
                        part.text
                        for part in event.content.parts
                        if part.text
                    )
        finally:
            if dataset_token is not None:
                reset_current_business_data(dataset_token)

            reset_current_actor(actor_token)

        if not response_text:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The agent did not return a text response.",
            )

        return {
            "success": True,
            "response": "\n".join(response_text),
            "organization_id": actor.organization_id,
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception("Agent chat request failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The agent request could not be completed.",
        ) from None
