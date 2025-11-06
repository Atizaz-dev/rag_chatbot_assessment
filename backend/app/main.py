import asyncio
import json
import logging
from typing import Dict

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse

from .pdfs import validate_pdf_upload, parse_pdf_bytes, PDFParseError
from .agent import agent
from .schemas import AgentRequest

logger = logging.getLogger("uvicorn.error")
app = FastAPI(title="Streaming Chatbot (FastAPI + Agno + NiceGUI)")

# Simple in-memory store for parsed PDFs for demo. In prod, use DB or Agno knowledge indexing.
parsed_pdfs: Dict[str, Dict] = {}

@app.post("/v1/pdf/upload", status_code=201)
async def upload_pdf(file: UploadFile = File(...)):
    MAX_FILE_SIZE = 500 * 1024
    data = await validate_pdf_upload(file)
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large. Max {MAX_FILE_SIZE // 1024} KB allowed.")

    try:
        text, meta, pdf_id = parse_pdf_bytes(data, file.filename)
    except PDFParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    # store
    parsed_pdfs[pdf_id] = {"metadata": meta.dict(), "text": text}

    # --- Push to Agno knowledge index ---
    try:
        await agent.client.add_document(
            doc_id=pdf_id,
            text=text,
            metadata=meta.dict()
        )
    except Exception as e:
        logger.error(f"Failed to push PDF {pdf_id} to Agno index: {e}")

    return {"pdf_id": pdf_id, "metadata": meta.dict()}


async def _stream_generator(req: AgentRequest):
    full_prompt = req.prompt
    if req.pdf_ids:
        pdf_texts = [parsed_pdfs[pid]["text"] for pid in req.pdf_ids if pid in parsed_pdfs]
        if pdf_texts:
            full_prompt += "\n\nPDF CONTENT:\n" + "\n\n".join(pdf_texts)

    new_req = AgentRequest(prompt=full_prompt)

    async for chunk in agent.stream_response(new_req):
        # chunk.chunk is ALREADY a single token/character from agent.py
        # We just need to wrap it in the SSE event format.
        event = json.dumps({"chunk": chunk.chunk, "final": False})
        yield f"data: {event}\n\n"
        await asyncio.sleep(0) # Keep this to allow FastAPI/uvicorn to flush the buffer

    # signal final event
    yield f"data: {json.dumps({'chunk':'', 'final':True})}\n\n"


@app.post("/v1/agent/stream")
async def agent_stream(request: AgentRequest):
    # Validate optional pdf ids exist
    if request.pdf_ids:
        for pid in request.pdf_ids:
            if pid not in parsed_pdfs:
                return JSONResponse(status_code=404, content={"detail": f"PDF {pid} not found"})
    # return SSE streaming response
    return StreamingResponse(_stream_generator(request), media_type="text/event-stream")
