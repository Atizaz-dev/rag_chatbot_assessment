import asyncio
import logging
from agno.agent import Agent
from agno.models.groq import Groq
from .schemas import AgentRequest, AgentChunk

logger = logging.getLogger(__name__)
OPENAI_API_KEY="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"
GROQ_API_KEY="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"

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
