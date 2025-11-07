from pydantic import BaseModel


class AgentRequest(BaseModel):
    session_id: str | None = None
    prompt: str
    pdf_ids: list[str] | None = None  # optional references to parsed PDFs


class AgentChunk(BaseModel):
    chunk: str
    final: bool = False
    session_id: str | None = None


class PDFMetadata(BaseModel):
    filename: str
    pages: int
    title: str | None = None
    author: str | None = None
    text_length: int = 0
    pdf_id: str
