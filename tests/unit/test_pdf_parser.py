import pytest
import pytest_check as check
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.pdfs import validate_pdf_upload, parse_pdf_bytes, PDFParseError

# pytestmark = pytest.mark.asyncio


def load_file_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def test_parse_sample_pdf(tmp_path):
    data = load_file_bytes("tests/data/git_rules_testing.pdf")
    text, meta, pdf_id = parse_pdf_bytes(data, "git_rules_testing.pdf")
    check.greater(len(text), 0)
    check.is_true(meta.pages >= 1)
    check.is_true(isinstance(pdf_id, str))


def test_parse_empty_pdf_raises():
    data = load_file_bytes("tests/data/blank.pdf")
    with pytest.raises(PDFParseError):
        parse_pdf_bytes(data, "blank.pdf")


def test_validate_upload_rejects_nonpdf(tmp_path):
    class Dummy:
        filename = "file.txt"

        async def read(self):
            return b"hello"

    with pytest.raises(Exception):
        # expecting HTTPException
        import asyncio

        asyncio.get_event_loop().run_until_complete(validate_pdf_upload(Dummy()))


def test_upload_endpoint_returns_400_on_empty_file(tmp_path):
    # Create dummy empty PDF
    dummy_file = tmp_path / "blank.pdf"
    dummy_file.write_bytes(b"")

    client = TestClient(app)
    with open(dummy_file, "rb") as f:
        response = client.post(
            "/v1/pdf/upload", files={"file": ("blank.pdf", f, "application/pdf")}
        )

    assert response.status_code == 400
    assert "empty" in response.text.lower()
