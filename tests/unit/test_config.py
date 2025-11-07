import asyncio
import inspect
import os
import pytest_check as check
from backend.app.config import settings
from backend.app.agent import AgnoAgent


def test_settings_loaded():
    """Ensure config properties exist and are typed."""
    check.is_instance(settings.max_pdf_bytes, int)


def test_agent_instantiation():
    """
    Tests that the AgnoAgent class can be instantiated and that its
    stream_response method returns an async generator.
    """
    # Get API key from environment or use a dummy for testing
    api_key = os.getenv("OPENAI_API_KEY", "test-key")
    
    # Test that the agent can be created successfully
    a = AgnoAgent(openai_api_key=api_key)
    check.is_instance(a, AgnoAgent)

    # Test that stream_response behaves as expected
    async def iter_one():
        gen = a.stream_response(prompt="hi", context="", history=[])
        assert inspect.isasyncgen(gen)
        count = 0
        async for _ in gen:
            count += 1
            if count > 10:
                break

    # Use asyncio.run to execute the async helper function
    asyncio.run(iter_one())