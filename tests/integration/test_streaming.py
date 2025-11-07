import pytest
import io
import json
from pathlib import Path
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from backend.app.main import app

pytestmark = pytest.mark.asyncio

TESTS_DIR = Path(__file__).parent
DATA_DIR = TESTS_DIR / "data"


async def test_full_workflow_upload_and_query():
    """
    Integration Test:
    1. Uploads a PDF to the /v1/pdf/upload endpoint.
    2. Receives a pdf_id.
    3. Sends a prompt and the pdf_id to the /v1/agent/stream endpoint.
    4. Verifies the streamed response contains content from the PDF.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # --- 1. UPLOAD ---
        pdf_path = DATA_DIR / "git_rules_testing.pdf"  # This is your PDF
        files = {"file": (pdf_path.name, open(pdf_path, "rb"), "application/pdf")}

        upload_response = await client.post("/v1/pdf/upload", files=files)

        assert upload_response.status_code == 201, upload_response.text
        upload_data = upload_response.json()
        assert "pdf_id" in upload_data
        pdf_id = upload_data["pdf_id"]

        # --- 2. QUERY ---
        prompt = "In what kind of branch should new features be developed?"
        query_payload = {
            "prompt": prompt,
            "pdf_ids": [pdf_id]
        }

        stream_response = await client.post("/v1/agent/stream", json=query_payload)

        assert stream_response.status_code == 200, stream_response.text

        # --- 3. VERIFY ANSWER ---
        full_response_text = ""
        final_chunk_received = False
        thinking_received = False
        
        async for line in stream_response.aiter_lines():
            if line.startswith("data: "):
                try:
                    data = json.loads(line[6:])
                    event_type = data.get("event", "answer")  # Default to "answer" for backward compat
                    
                    # Handle thinking event
                    if event_type == "thinking":
                        thinking_received = True
                        thinking_text = data.get("thinking", "")
                        assert len(thinking_text) > 0, "Thinking should contain text"
                    
                    # Handle answer chunks
                    elif event_type == "answer":
                        chunk = data.get("chunk", "")
                        full_response_text += chunk
                        if data.get("final"):
                            final_chunk_received = True
                    else:
                        # Fallback for old format (no event field)
                        full_response_text += data.get("chunk", "")
                        if data.get("final"):
                            final_chunk_received = True
                            
                except json.JSONDecodeError:
                    continue

        assert final_chunk_received, "Should receive final chunk"
        assert "feature" in full_response_text.lower(), f"Response should mention 'feature', got: {full_response_text[:200]}"

        # This assertion is still valuable
        assert "unable to" not in full_response_text.lower()


async def test_upload_oversized_file():
    """
    Error Test: Ensures uploading a file larger than the configured
    limit returns a 413 Payload Too Large error.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Your limit in main.py is 2MB. We create a fake file larger than that.
        oversized_content = b"a" * (2 * 1024 * 1024 + 1)
        oversized_file = io.BytesIO(oversized_content)

        files = {"file": ("oversized.pdf", oversized_file, "application/pdf")}

        response = await client.post("/v1/pdf/upload", files=files)

        assert response.status_code == 413
        assert "File too large" in response.json()["detail"]