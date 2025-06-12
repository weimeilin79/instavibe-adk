from a2a.server.apps import A2AStarletteApplication
from a2a.types import AgentCard, AgentCapabilities, AgentSkill
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.request_handlers import DefaultRequestHandler
import os
import logging
from dotenv import load_dotenv
from social.agent_executor import (
    SocialAgentExecutor,  
    SocialAgent,
)
import uvicorn

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

host=os.environ.get("A2A_HOST", "localhost")
port=int(os.environ.get("A2A_PORT",10001))
PUBLIC_URL=os.environ.get("PUBLIC_URL")

if __name__ == '__main__':
    try:
        capabilities = AgentCapabilities(streaming=True)
        skill = AgentSkill(
            id="social_profile_analysis",
            name="Analyze Instavibe social profile",
            description="""
            Using a provided list of names, this agent synthesizes Instavibe social profile information by analyzing posts, friends, and events.
            It delivers a comprehensive single-paragraph summary for individuals, and for groups, identifies commonalities in their social activities
            and connections based on profile data.
            """,
            tags=["instavibe"],
            examples=["Can you tell me about Bob and Alice?"],
        )
        agent_card = AgentCard(
            name="Social Profile Agent",
            description="""
            Using a provided list of names, this agent synthesizes Instavibe social profile information by analyzing posts, friends, and events.
            It delivers a comprehensive single-paragraph summary for individuals, and for groups, identifies commonalities in their social activities
            and connections based on profile data.
            """,
            url=f"{PUBLIC_URL}",
            version="1.0.0",
            defaultInputModes=SocialAgent.SUPPORTED_CONTENT_TYPES,
            defaultOutputModes=SocialAgent.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[skill],
        )
        request_handler = DefaultRequestHandler(
            agent_executor=SocialAgentExecutor(),
            task_store=InMemoryTaskStore(),
        )

        server = A2AStarletteApplication(
            agent_card=agent_card,
            http_handler=request_handler,
        )

        uvicorn.run(server.build(), host='0.0.0.0', port=port)
    except Exception as e:
        logger.error(f"An error occurred during server startup: {e}")
        exit(1)

