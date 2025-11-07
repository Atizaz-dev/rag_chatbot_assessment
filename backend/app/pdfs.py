import io
import os
import uuid
import logging
from pypdf import PdfReader
from fastapi import UploadFile, HTTPException
from .config import settings
from .schemas import PDFMetadata

logger = logging.getLogger(__name__)

TEXT_STORAGE_DIR = "pdf_text"
os.makedirs(TEXT_STORAGE_DIR, exist_ok=True)


class PDFParseError(Exception):
    pass


async def validate_pdf_upload(upload: UploadFile) -> bytes:
    data = await upload.read()
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > settings.max_pdf_bytes:
        raise HTTPException(status_code=413, detail="File too large")
    # Basic filename check
    if not upload.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Unsupported file type (only .pdf)")
    logger.debug(
        "validate_pdf_upload ok | filename=%s size=%dB", upload.filename, len(data)
    )
    return data


def save_parsed_text_to_file(pdf_id: str, text: str) -> str:
    """Save parsed text to local directory."""
    file_path = os.path.join(TEXT_STORAGE_DIR, f"{pdf_id}.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(text)
    return file_path


def parse_pdf_bytes(data: bytes, filename: str) -> tuple[str, PDFMetadata, str]:
    """
    Parse bytes into text and metadata.
    Returns (text, metadata, pdf_id)
    """
    try:
        logger.info("parse_pdf_bytes start | filename=%s size=%dB", filename, len(data))
        buf = io.BytesIO(data)
        reader = PdfReader(buf)
        pages = len(reader.pages)
        text_chunks = []
        for p in reader.pages:
            text_chunks.append(p.extract_text() or "")
        text = "\n".join(text_chunks).strip()
        if not text:
            raise PDFParseError("Parsed PDF is empty")
        metadata = reader.metadata or {}
        pdf_id = str(uuid.uuid4())
        meta = PDFMetadata(
            filename=filename,
            pages=pages,
            title=metadata.get("/Title") if isinstance(metadata, dict) else None,
            author=metadata.get("/Author") if isinstance(metadata, dict) else None,
            text_length=len(text),
            pdf_id=pdf_id,
        )
        save_parsed_text_to_file(pdf_id, text)
        logger.info(
            "parse_pdf_bytes done | pdf_id=%s pages=%d text_len=%d",
            pdf_id,
            pages,
            len(text),
        )
        return text, meta, pdf_id
    except Exception as exc:
        logger.exception("PDF parsing failed")
        raise PDFParseError(str(exc)) from exc
