import logging
from collections.abc import AsyncGenerator
from typing import Any

from pydantic import PrivateAttr

from google.adk.models import Gemini
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse

logger = logging.getLogger(__name__)


class FallbackGemini(BaseLlm):
    """Try a primary Gemini model, falling back only before output begins."""

    fallback_model: str

    _primary: Gemini = PrivateAttr()
    _fallback: Gemini = PrivateAttr()

    def __init__(self, *, model: str, fallback_model: str) -> None:
        super().__init__(model=model, fallback_model=fallback_model)
        self._primary = Gemini(model=model)
        self._fallback = Gemini(model=fallback_model)

    @classmethod
    def supported_models(cls) -> list[str]:
        """Match only the explicit primary model configured for this agent."""
        return [r"gemini-flash-lite-latest"]

    async def generate_content_async(
        self,
        llm_request: LlmRequest,
        stream: bool = False,
    ) -> AsyncGenerator[LlmResponse, None]:
        """Use the fallback only if the primary fails before yielding output."""

        primary_request = llm_request.model_copy(deep=True)
        primary_request.model = self.model

        response_started = False

        try:
            async for response in self._primary.generate_content_async(
                primary_request,
                stream=stream,
            ):
                response_started = True
                yield response
            return

        except Exception as exc:
            if response_started:
                logger.exception(
                    "Primary Gemini model failed after output began; "
                    "not retrying to avoid duplicate responses."
                )
                raise

            logger.warning(
                "Primary Gemini model failed before producing output (%s). "
                "Trying configured fallback model.",
                type(exc).__name__,
            )

        fallback_request = llm_request.model_copy(deep=True)
        fallback_request.model = self.fallback_model

        async for response in self._fallback.generate_content_async(
            fallback_request,
            stream=stream,
        ):
            yield response
