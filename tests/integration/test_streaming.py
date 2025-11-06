import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

# @pytest.mark.asyncio
def test_streaming_endpoint_returns_multiple_chunks():
    client = TestClient(app)
    prompt = "Hello, can you summarize the PDF content?"

    # Open a streaming request to the endpoint
    with client.stream("POST", "/v1/agent/stream", json={"prompt": prompt}) as response:
        assert response.status_code == 200

        chunks = []
        for chunk in response.iter_lines():
            if chunk:
                chunks.append(chunk.encode("utf-8"))

        # Ensure multiple chunks are streamed (not just one)
        assert len(chunks) > 1, f"Expected multiple chunks, got {len(chunks)}"
        print("Streamed chunks:", chunks)
