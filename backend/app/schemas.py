from pydantic import BaseModel, Field
from typing import List, Optional

class AgentRequest(BaseModel):
    session_id: Optional[str] = None
    prompt: str
    pdf_ids: Optional[List[str]] = None  # optional references to parsed PDFs

class AgentChunk(BaseModel):
    chunk: str
    final: bool = False

class PDFMetadata(BaseModel):
    filename: str
    pages: int
    title: Optional[str] = None
    author: Optional[str] = None
    text_length: int = 0
    pdf_id: str
