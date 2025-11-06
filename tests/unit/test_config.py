import pytest_check as check
from backend.app.config import settings
from backend.app.agent import AgnoAgent

def test_settings_loaded():
    # Ensure config properties exist and are typed
    check.is_instance(settings.max_pdf_bytes, int)

def test_agent_instantiation():
    a = AgnoAgent()
    check.is_instance(a, AgnoAgent)
    # streaming should be an async generator when called
    import inspect, asyncio
    async def iter_one():
        gen = a.stream_response(type("R", (), {"prompt": "hi", "session_id": None, "pdf_ids": None})())
        assert inspect.isasyncgen(gen)

    # Use asyncio.run instead of get_event_loop().run_until_complete
    asyncio.run(iter_one())
