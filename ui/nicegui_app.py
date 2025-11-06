import mimetypes
import asyncio
import json
import httpx
from nicegui import ui


BACKEND_URL = "http://localhost:8000"

# ------------------------------
# State
# ------------------------------
uploaded_pdfs = []
chat_history = []
message_queue = []

# ------------------------------
# Functions
# ------------------------------
def set_status(text: str | None):
    status_label.set_text(text or "")

# Timer to update message box safely from background
def update_message_box():
    if message_queue:  # only 1 token per tick
        message_box.set_content(message_box.content + message_queue.pop(0))

ui.timer(0.01, update_message_box)  # 50ms per token

# ------------------------------
# PDF Upload
# ------------------------------
async def upload_pdf_handler(e):
    file = e.file
    content = await file.read()
    mime = mimetypes.guess_type(file.name)[0] or "application/pdf"

    MAX_FILE_SIZE = 500 * 1024  # 500 KB limit

    if len(content) == 0:
        ui.notify("Empty file uploaded.", color="negative")
        return
    if len(content) > MAX_FILE_SIZE:
        ui.notify(f"File too large. Max {MAX_FILE_SIZE // 1024} KB allowed.", color="negative")
        return

    files = {"file": (file.name, content, mime)}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BACKEND_URL}/v1/pdf/upload", files=files)

    if r.status_code == 201:
        pdf_info = r.json()
        uploaded_pdfs.append(pdf_info["pdf_id"])
        ui.notify(f"Uploaded: {pdf_info['pdf_id']}")
    else:
        try:
            error_msg = r.json().get("detail")  # only detail
        except Exception:
            error_msg = r.text  # fallback
        ui.notify(f"{error_msg}", color="negative")

# ------------------------------
# Chat
# ------------------------------
async def start_chat():
    prompt = prompt_input.value.strip()
    if not prompt:
        set_status("Enter a prompt!")
        return

    # Clear previous messages
    message_box.set_content("")
    set_status("Analyzing...")
    await asyncio.sleep(0.2)
    set_status("Searching...")
    await asyncio.sleep(0.2)
    set_status("Generating...")

    data = {"prompt": prompt, "pdf_ids": uploaded_pdfs}

    async with httpx.AsyncClient(timeout=None) as client:
        try:
            r = await client.post(f"{BACKEND_URL}/v1/agent/stream", json=data)
            if r.status_code != 200:
                set_status(f"Error: {r.status_code}")
                return
        except Exception as e:
            set_status(f"Connection error: {e}")
            return

        set_status("Generating...")

        async for line in r.aiter_lines():
            if not line.startswith("data: "):
                continue

            payload_str = line[6:]
            if not payload_str.strip():
                continue

            try:
                payload = json.loads(payload_str)
            except json.JSONDecodeError:
                continue

            if "error" in payload:
                set_status(f"Agent error: {payload['error']}")
                return

            chunk = payload.get("chunk", "")
            final = payload.get("final", False)

            if chunk:
                # enqueue each token for smooth streaming
                for token in chunk:
                    message_queue.append(token)

            if final:
                set_status("")
                chat_history.append({"prompt": prompt, "response": message_box.content})
                break

# ------------------------------
# UI
# ------------------------------
with ui.row():
    ui.label("PDF Upload").style("margin-right: 12px;")
    upload = ui.upload(on_upload=upload_pdf_handler, max_files=1)
    ui.button("Open Chat", on_click=lambda: chat_dialog.open())

chat_dialog = ui.dialog()
with chat_dialog:
    with ui.card():
        ui.label("Streaming Chat").style("font-weight: 600")
        prompt_input = ui.input("Enter prompt")
        with ui.row():
            ui.button("Start", on_click=lambda: asyncio.ensure_future(start_chat()))
            status_label = ui.label("")
        message_box = ui.markdown("")
        ui.button("Close", on_click=chat_dialog.close)

# Run NiceGUI
ui.run(reload=True, title="Agno Streaming Demo")
