import json
from fastapi.testclient import TestClient
from backend.app.main import app

def test_upload_parse_query_stream():
    client = TestClient(app)

    # Step 1: Upload PDF
    with open("tests/data/git_rules_testing.pdf", "rb") as f:
        upload_response = client.post(
            "/v1/pdf/upload",
            files={"file": ("sample.pdf", f, "application/pdf")}
        )
        assert upload_response.status_code == 201
        pdf_id = upload_response.json()["pdf_id"]

    # Step 2: Stream agent response referencing PDF
    prompt = "Please summarize the PDF content."
    with client.stream(
        "POST",
        "/v1/agent/stream",
        json={"prompt": prompt, "pdf_ids": [pdf_id]}
    ) as response:
        assert response.status_code == 200

        chunks = []
        for line in response.iter_lines():
            if not line:
                continue
            if isinstance(line, bytes):
                line = line.decode("utf-8")
            data = json.loads(line.removeprefix("data: ").strip())
            if not data["final"]:
                chunks.append(data["chunk"])

    # Step 3: Assert multiple chunks
    assert len(chunks) > 1, f"Expected multiple chunks, got {len(chunks)}"
    print("Streamed chunks:", chunks)
