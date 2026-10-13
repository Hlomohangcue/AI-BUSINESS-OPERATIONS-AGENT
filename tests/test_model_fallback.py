import asyncio
import pytest

from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse

from src.agents.model_fallback import FallbackGemini


PRIMARY = "gemini-flash-lite-latest"
FALLBACK = "gemini-3.5-flash"


class FakeModel:
    def __init__(self, responses=None, error=None):
        self.responses = responses or []
        self.error = error
        self.calls = []

    async def generate_content_async(self, request, stream=False):
        self.calls.append((request.model, stream))

        if self.error:
            raise self.error

        for response in self.responses:
            yield response


def make_agent(monkeypatch):
    agent = FallbackGemini(model=PRIMARY, fallback_model=FALLBACK)
    primary = FakeModel()
    fallback = FakeModel()

    monkeypatch.setattr(agent, "_primary", primary)
    monkeypatch.setattr(agent, "_fallback", fallback)

    return agent, primary, fallback


def test_primary_success_does_not_call_fallback(monkeypatch):
    async def scenario():
        agent, primary, fallback = make_agent(monkeypatch)
        expected = LlmResponse()
        primary.responses = [expected]

        results = [
            response
            async for response in agent.generate_content_async(
                LlmRequest(model=PRIMARY)
            )
        ]

        assert results == [expected]
        assert primary.calls == [(PRIMARY, False)]
        assert fallback.calls == []

    asyncio.run(scenario())


def test_primary_failure_uses_fallback(monkeypatch):
    async def scenario():
        agent, primary, fallback = make_agent(monkeypatch)
        expected = LlmResponse()
        primary.error = RuntimeError("primary unavailable")
        fallback.responses = [expected]

        results = [
            response
            async for response in agent.generate_content_async(
                LlmRequest(model=PRIMARY)
            )
        ]

        assert results == [expected]
        assert primary.calls == [(PRIMARY, False)]
        assert fallback.calls == [(FALLBACK, False)]

    asyncio.run(scenario())


def test_both_models_failing_surfaces_fallback_error(monkeypatch):
    async def scenario():
        agent, primary, fallback = make_agent(monkeypatch)
        primary.error = RuntimeError("primary unavailable")
        fallback.error = RuntimeError("fallback unavailable")

        with pytest.raises(RuntimeError, match="fallback unavailable"):
            async for _ in agent.generate_content_async(
                LlmRequest(model=PRIMARY)
            ):
                pass

        assert primary.calls == [(PRIMARY, False)]
        assert fallback.calls == [(FALLBACK, False)]

    asyncio.run(scenario())


def test_primary_failure_after_output_does_not_retry(monkeypatch):
    async def scenario():
        agent, primary, fallback = make_agent(monkeypatch)
        first_response = LlmResponse()

        async def response_then_error(request, stream=False):
            primary.calls.append((request.model, stream))
            yield first_response
            raise RuntimeError("connection lost after output")

        primary.generate_content_async = response_then_error
        results = []

        with pytest.raises(RuntimeError, match="connection lost after output"):
            async for response in agent.generate_content_async(
                LlmRequest(model=PRIMARY),
                stream=True,
            ):
                results.append(response)

        assert results == [first_response]
        assert fallback.calls == []

    asyncio.run(scenario())


def test_registry_still_uses_builtin_gemini_for_now():
    from google.adk.models.registry import LLMRegistry
    from google.adk.models import Gemini

    assert LLMRegistry.resolve(PRIMARY) is Gemini
