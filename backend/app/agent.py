import logging
import asyncio
import os
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from sqlalchemy import text

from .schemas import AgentChunk
from .db.memories import add_memory
from .db.memory_utils import extract_memories_from_text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://ai:ai@localhost:5432/ai")

engine = create_async_engine(DATABASE_URL, future=True, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def test_db_connection():
    try:
        async with engine.connect() as conn:
            # run a lightweight query to verify connection
            await conn.execute(text("SELECT 1"))
        logger.info("✅ Database connected successfully to %s", DATABASE_URL)
    except Exception as e:
        logger.exception("❌ Database connection failed: %s", e)


class AgnoAgent:
    def __init__(self, openai_api_key: str):
        self.db = None
        self.agent = Agent(model=OpenAIChat(id="gpt-4o-mini", api_key=openai_api_key),  enable_user_memories=False)
        logger.info("AgnoAgent initialized (user memories disabled)")

        try:
            try:
                # Try to get running loop (Python 3.7+)
                loop = asyncio.get_running_loop()
                # If we get here, we're in an async context - schedule background task
                asyncio.create_task(test_db_connection())
                logger.info("Scheduled DB connection test (event loop already running).")
            except RuntimeError:
                # No running loop - try to get or create one
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Loop is running but get_running_loop() failed - schedule task
                        asyncio.create_task(test_db_connection())
                        logger.info("Scheduled DB connection test (event loop already running).")
                    else:
                        # Loop exists but not running - run until complete
                        loop.run_until_complete(test_db_connection())
                        logger.info("Completed DB connection test synchronously.")
                except RuntimeError:
                    # No event loop at all - create a new one
                    new_loop = asyncio.new_event_loop()
                    try:
                        asyncio.set_event_loop(new_loop)
                        new_loop.run_until_complete(test_db_connection())
                        logger.info("Completed DB connection test on a new event loop.")
                    finally:
                        new_loop.close()
        except Exception as e:
            logger.exception("Error while attempting to test DB connection: %s", e)

    async def stream_response(self, prompt: str, context: str, history: list[dict[str, str]], user_id: str | None = None):
        """
        Streams response. If user_id is provided, the caller should have already
        loaded the memories into `context`. After the final response we attempt to
        extract and persist new memories.
        """
        final_prompt = prompt
        logger.debug("stream_response called | user_id=%s history_len=%d context_chars=%d", user_id, len(history or []), len(context or ""))
        if context:
            final_prompt = (
                "You are an assistant that answers questions based ONLY on the context provided below.\n"
                "You need to analyze the context of the user clearly and try to answere the user query if the answere is out of context, 'I cannot find the answere in the provided document'\n\n"
                "--- CONTEXT ---\n"
                f"{context}\n"
                "--- END CONTEXT ---\n\n"
                f"QUESTION: {prompt}"
            )

        try:
            response_stream = self.agent.run(input=final_prompt, history=history, stream=True, user_id=user_id)

            full_text = ""
            for event in response_stream:
                if hasattr(event, "content") and event.content:
                    chunk = event.content
                    full_text += chunk
                    yield AgentChunk(chunk=chunk, final=False)
                await asyncio.sleep(0.01)

            # finished
            yield AgentChunk(chunk="", final=True)

            # simple memory extraction from user prompt + assistant answer
            if user_id:
                # combine user prompt & assistant response to look for new facts
                combined = prompt + "\n\n" + full_text
                new_mems = extract_memories_from_text(combined)

                # Save only concise extracted memories (not raw characters)
                for mem in new_mems:
                    try:
                        await add_memory(user_id=user_id, memory_text=mem)
                        logger.info("Added memory for user %s: %s", user_id, mem)
                    except Exception:
                        logger.exception("Failed to add memory")
            logger.info("Finished streaming response | user_id=%s total_chars=%d", user_id, len(full_text))
        except Exception as e:
            logger.exception("Error streaming response: %s", e)
            yield AgentChunk(chunk=f"Error: {e}", final=True)


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
agent = AgnoAgent(OPENAI_API_KEY)
