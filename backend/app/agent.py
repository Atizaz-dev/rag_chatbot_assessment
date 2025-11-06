import os
import asyncio
import logging
from agno.agent import Agent
from agno.models.groq import Groq
from .schemas import AgentRequest, AgentChunk
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

logger = logging.getLogger(__name__)

#Agno handles conversation context internally; session history may be added later via Agno’s built-in memory.
class AgnoAgent:
    def __init__(self):
        # self.agent = Agent(
        #     model=OpenAIChat(id="gpt-4o-mini", api_key=OPENAI_API_KEY)
        # )
        self.agent = Agent(
            model=Groq(
                id="llama-3.3-70b-versatile",
                api_key=GROQ_API_KEY,
            )
        )
        logger.info("AgnoAgent initialized using OpenAIChat")

    async def stream_response(self, request: AgentRequest):
        """Yield token by token"""
        response = self.agent.run(input=request.prompt, stream=True)
        for event in response:
            text = getattr(event, "content", "")
            for token in text:
                yield AgentChunk(chunk=token, final=False)
            await asyncio.sleep(0)
        yield AgentChunk(chunk="", final=True)


agent = AgnoAgent()
