import json
import asyncio
import mimetypes
import httpx
from nicegui import ui

# Define the backend URL
BACKEND_URL = "http://localhost:8001"  # Replace with your actual backend URL

# State to keep track of the uploaded PDFs and chat history
uploaded_pdfs = []
chat_history = []  # List to hold the conversation history for display

message_queue = []  # This will be used for streaming the response smoothly

# Set the status text for the chat UI
def set_status(text: str | None):
    status_label.set_text(text or "")

# Function to update message box as new tokens arrive
def update_message_box():
    if message_queue:  # Only 1 token per tick
        message_box.set_content(message_box.content + message_queue.pop(0))

ui.timer(0.01, update_message_box)  # Timer for smooth streaming

# Handle PDF upload
async def upload_pdf_handler(e):
    file = e.file
    content = await file.read()
    mime = mimetypes.guess_type(file.name)[0] or "application/pdf"
    MAX_FILE_SIZE = 500 * 1024

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
        uploaded_pdfs.append(pdf_info["pdf_id"])  # Ensure pdf_id is added correctly
        ui.notify(f"Uploaded: {pdf_info['pdf_id']}")
    else:
        ui.notify(f"Upload failed: {r.text}", color="negative")

# Start a new chat with the backend
async def start_chat():
    prompt = prompt_input.value.strip()
    if not prompt:
        set_status("Enter a prompt!")
        return

    # Add user's prompt to chat history
    chat_history.append({"role": "user", "message": prompt})

    # Clear previous messages and set status to analyzing
    thinking_box.set_content("")
    message_box.set_content("")
    set_status("Analyzing...")
    await asyncio.sleep(0.2)
    set_status("Searching...")
    await asyncio.sleep(0.2)
    set_status("Generating...")

    # Prepare the request data, including the full chat history
    data = {"prompt": prompt, "pdf_ids": uploaded_pdfs, "chat_history": chat_history}

    # Make an async request to the backend to stream the agent's response
    async with httpx.AsyncClient(timeout=None) as client:
        try:
            r = await client.post(f"{BACKEND_URL}/v1/agent/stream?user_id=123", json=data)
            if r.status_code != 200:
                set_status(f"Error: {r.status_code}")
                return
        except Exception as e:
            set_status(f"Connection error: {e}")
            return

        set_status("Generating...")

        # Process the streamed response from the agent
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

            event_type = payload.get("event")
            if event_type == "thinking":
                thinking = payload.get("thinking", "")
                if thinking:
                    thinking_box.set_content(f"### Thinking\n{thinking}")
                continue

            chunk = payload.get("chunk", "")
            final = payload.get("final", False)

            if chunk:
                # Enqueue each token for smooth streaming
                for token in chunk:
                    message_queue.append(token)

            if final:
                set_status("")
                # Add the chatbot's response to chat history
                chat_history.append({"role": "assistant", "message": message_box.content})
                break

# Define the UI elements
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
        thinking_box = ui.markdown("")
        message_box = ui.markdown("")
        ui.button("Close", on_click=chat_dialog.close)

# Run the NiceGUI UI
ui.run(reload=True, title="Agno Streaming Demo")
