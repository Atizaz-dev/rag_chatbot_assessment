import asyncio
import json
import logging
import uuid

from .schemas import AgentRequest
from .agent import agent
from .db.memories import get_user_memories
from .vector_store import (
    async_store_pdf_embeddings,
    retrieve_relevant_chunks,
    cleanup_embeddings,
)

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse

from .pdfs import (
    validate_pdf_upload,
    parse_pdf_bytes,
    PDFParseError,
    cleanup_text_files,
)


logger = logging.getLogger("uvicorn.error")
app = FastAPI(title="Streaming Chatbot (FastAPI + Agno + NiceGUI)")

# This dictionary is now the definitive source of truth for PDF content.
parsed_pdfs: dict[str, dict] = {}
chat_histories: dict[str, list[dict[str, str]]] = {}


@app.post("/v1/pdf/upload", status_code=201)
async def upload_pdf(file: UploadFile = File(...)):
    MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB
    data = await validate_pdf_upload(file)
    logger.info("upload_pdf received | filename=%s size=%dB", file.filename, len(data))
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large...")

    try:
        text, meta, pdf_id = parse_pdf_bytes(data, file.filename)
    except PDFParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Keep only the most recently uploaded document
    parsed_pdfs.clear()
    cleanup_text_files(pdf_id)
    cleanup_embeddings(pdf_id)

    # Store the parsed PDF text in our application's memory
    parsed_pdfs[pdf_id] = {"metadata": meta.model_dump(), "text": text}
    logger.info(
        "upload_pdf parsed | pdf_id=%s pages=%d text_len=%d",
        pdf_id,
        meta.pages,
        len(text),
    )

    # Generate and persist embeddings asynchronously (best-effort)
    try:
        await async_store_pdf_embeddings(pdf_id, text)
    except Exception as exc:  # pragma: no cover - external API call
        logger.exception("Failed to store embeddings for %s: %s", pdf_id, exc)

    return {"pdf_id": pdf_id, "metadata": meta.model_dump()}


async def _stream_generator(req: AgentRequest, user_id: str | None):
    session_id = req.session_id or str(uuid.uuid4())
    history = chat_histories.get(session_id, [])

    context_parts = []

    # PDFs via embeddings (fallback to raw text if embeddings unavailable)
    if req.pdf_ids:
        chunk_snippets = retrieve_relevant_chunks(req.pdf_ids, req.prompt, top_k=5)
        if chunk_snippets:
            context_parts.append(
                "Relevant document excerpts:\n" + "\n\n".join(chunk_snippets)
            )
        else:
            pdf_texts = [
                parsed_pdfs[pid]["text"] for pid in req.pdf_ids if pid in parsed_pdfs
            ]
            if pdf_texts:
                context_parts.append("\n\n".join(pdf_texts))

    # Memories (limit to most recent N to avoid drowning document context)
    if user_id:
        try:
            RECENT_MEM_LIMIT = 15
            mems = await get_user_memories(user_id=user_id, limit=RECENT_MEM_LIMIT)
            if mems:
                mem_str = "User memories (recent):\n" + "\n".join(
                    f"- {m.memory_text}" for m in mems[-RECENT_MEM_LIMIT:]
                )
                context_parts.append(mem_str)
        except Exception as e:
            logger.exception(f"Failed reading memories for user {user_id}: {e}")

    context_str = "\n\n".join(context_parts)

    logger.info(
        "stream start | session_id=%s user_id=%s pdf_ids=%d",
        session_id,
        user_id,
        len(req.pdf_ids or []),
    )
    # Emit a brief "thinking" rationale before the final answer
    try:
        thinking_text = await agent.generate_thinking(
            prompt=req.prompt,
            context=context_str,
            history=history,
        )
        thinking_event = json.dumps(
            {
                "event": "thinking",
                "thinking": thinking_text,
                "final": False,
                "session_id": session_id,
            }
        )
        yield f"data: {thinking_event}\n\n"
        await asyncio.sleep(0.01)
    except Exception:
        # Non-fatal if thinking fails
        pass

    full_response = ""
    async for chunk in agent.stream_response(
        prompt=req.prompt, context=context_str, history=history, user_id=user_id
    ):
        full_response += chunk.chunk
        event = json.dumps(
            {
                "event": "answer",
                "chunk": chunk.chunk,
                "final": chunk.final,
                "session_id": session_id,
            }
        )
        yield f"data: {event}\n\n"
        await asyncio.sleep(0.01)

    if session_id not in chat_histories:
        chat_histories[session_id] = []

    chat_histories[session_id].append({"role": "user", "content": req.prompt})
    chat_histories[session_id].append({"role": "assistant", "content": full_response})
    logger.info(
        "stream end | session_id=%s response_chars=%d turns=%d",
        session_id,
        len(full_response),
        len(chat_histories[session_id]),
    )


# endpoint
@app.post("/v1/agent/stream")
async def agent_stream(request: AgentRequest, user_id: str | None = None):
    logger.info(
        "agent_stream request | user_id=%s pdf_ids=%d",
        user_id,
        len(request.pdf_ids or []),
    )
    if request.pdf_ids:
        valid_ids = [pid for pid in request.pdf_ids if pid in parsed_pdfs]
        missing = set(request.pdf_ids) - set(valid_ids)
        if missing:
            logger.info("Dropping missing pdf_ids from request: %s", ", ".join(missing))
        if request.pdf_ids and not valid_ids:
            return JSONResponse(
                status_code=404,
                content={"detail": "No uploaded PDFs found for this request."},
            )
        request.pdf_ids = valid_ids

    return StreamingResponse(
        _stream_generator(request, user_id=user_id),
        media_type="text/event-stream",
    )
