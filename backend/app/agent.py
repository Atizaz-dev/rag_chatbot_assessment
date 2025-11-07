import logging
import asyncio
import os
import json
import re
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
        self.agent = Agent(
            model=OpenAIChat(id="gpt-4o-mini", api_key=openai_api_key),
            enable_user_memories=False,
        )
        logger.info("AgnoAgent initialized (user memories disabled)")

        try:
            try:
                # Try to get running loop (Python 3.7+)
                loop = asyncio.get_running_loop()
                # If we get here, we're in an async context - schedule background task
                asyncio.create_task(test_db_connection())
                logger.info(
                    "Scheduled DB connection test (event loop already running)."
                )
            except RuntimeError:
                # No running loop - try to get or create one
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Loop is running but get_running_loop() failed - schedule task
                        asyncio.create_task(test_db_connection())
                        logger.info(
                            "Scheduled DB connection test (event loop already running)."
                        )
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

    async def stream_response(
        self,
        prompt: str,
        context: str,
        history: list[dict[str, str]],
        user_id: str | None = None,
    ):
        """
        Streams response. If user_id is provided, the caller should have already
        loaded the memories into `context`. After the final response we attempt to
        extract and persist new memories.
        """
        final_prompt = prompt
        logger.debug(
            "stream_response called | user_id=%s history_len=%d context_chars=%d",
            user_id,
            len(history or []),
            len(context or ""),
        )
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
            response_stream = self.agent.run(
                input=final_prompt, history=history, stream=True, user_id=user_id
            )

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
            logger.info(
                "Finished streaming response | user_id=%s total_chars=%d",
                user_id,
                len(full_text),
            )
        except Exception as e:
            logger.exception("Error streaming response: %s", e)
            yield AgentChunk(chunk=f"Error: {e}", final=True)

    async def generate_thinking(
        self, prompt: str, context: str, history: list[dict[str, str]]
    ) -> str:
        """Generate a brief, user-visible rationale before streaming the final answer.

        This avoids revealing chain-of-thought; instead it returns 2-4 short bullets
        summarizing the approach based on the provided context.
        """
        thinking_prompt = (
            "Provide a short rationale BEFORE answering.\n"
            "Rules:\n"
            "- 2 to 4 bullets\n"
            "- Each bullet <= 18 words\n"
            "- Do NOT include the final answer\n"
            '- Output ONLY JSON: {"thinking": ["point1", "point2"]}\n\n'
        )

        if context:
            thinking_prompt += (
                "--- CONTEXT ---\n" f"{context}\n" "--- END CONTEXT ---\n\n"
            )
        thinking_prompt += f"QUESTION: {prompt}"

        try:
            logger.debug(
                "generate_thinking called | history_len=%d context_chars=%d",
                len(history or []),
                len(context or ""),
            )
            # Explicitly request non-streaming output
            result = self.agent.run(
                input=thinking_prompt, history=history, stream=False
            )

            # Extract plain text from possible result shapes
            text_out = None
            # Case 1: direct string
            if isinstance(result, str):
                text_out = result
            # Case 2: object with .content
            elif hasattr(result, "content") and isinstance(
                getattr(result, "content"), str
            ):
                text_out = result.content
            else:
                # Case 3: iterable of events (collect .content)
                collected = []
                try:
                    for ev in result:  # type: ignore[assignment]
                        if hasattr(ev, "content") and isinstance(ev.content, str):
                            collected.append(ev.content)
                except TypeError:
                    # Not iterable; fall back to stringification
                    pass
                if collected:
                    text_out = "".join(collected)
                else:
                    # Last resort stringification
                    text_out = str(result)

            text_out = (text_out or "").strip()

            # Extract JSON from markdown code blocks if present
            json_match = re.search(
                r"```(?:json)?\s*(\{.*?\})\s*```", text_out, re.DOTALL
            )
            if json_match:
                text_out = json_match.group(1).strip()
            else:
                # Try to find JSON object in text (handles cases like "json {...}")
                json_match = re.search(
                    r'\{[^{}]*"thinking"[^{}]*\[[^\]]*\][^{}]*\}', text_out, re.DOTALL
                )
                if json_match:
                    text_out = json_match.group(0).strip()

            # Try strict JSON first
            try:
                obj = json.loads(text_out)
                thoughts = obj.get("thinking")
                if isinstance(thoughts, list) and thoughts:
                    bullets = [str(t).strip() for t in thoughts if str(t).strip()]
                    bullets = bullets[:4]
                    logger.debug(
                        "generate_thinking parsed JSON | bullets=%d", len(bullets)
                    )
                    return "\n".join(f"- {t}" for t in bullets)
            except (json.JSONDecodeError, AttributeError):
                # If JSON parsing fails, try to extract JSON object more aggressively
                try:
                    # Find the first { and last } to extract JSON
                    start = text_out.find("{")
                    end = text_out.rfind("}")
                    if start != -1 and end != -1 and end > start:
                        json_str = text_out[start : end + 1]
                        obj = json.loads(json_str)
                        thoughts = obj.get("thinking")
                        if isinstance(thoughts, list) and thoughts:
                            bullets = [
                                str(t).strip() for t in thoughts if str(t).strip()
                            ]
                            bullets = bullets[:4]
                            logger.debug(
                                "generate_thinking extracted JSON | bullets=%d",
                                len(bullets),
                            )
                            return "\n".join(f"- {t}" for t in bullets)
                except Exception:
                    pass

            # Fallback: pull bullet-like lines
            lines = [ln.strip() for ln in text_out.splitlines() if ln.strip()]
            bullet_lines = []
            for ln in lines:
                if ln.startswith(("-", "*")) or ln[:2].isdigit():
                    bullet_lines.append(ln.lstrip("-* ").strip())
                if len(bullet_lines) >= 4:
                    break
            if bullet_lines:
                logger.debug(
                    "generate_thinking fallback bullets | count=%d", len(bullet_lines)
                )
                return "\n".join(f"- {ln[:180]}" for ln in bullet_lines)

            # Final clamp if still messy
            short = text_out.replace("\n", " ")[:300]
            return (
                f"- {short}"
                if short
                else "- Analyzing context and identifying relevant sections"
            )
        except Exception as e:
            logger.exception("Thinking generation failed: %s", e)
            return "- Analyzing the question and matching it to relevant document parts"


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
agent = AgnoAgent(OPENAI_API_KEY)
