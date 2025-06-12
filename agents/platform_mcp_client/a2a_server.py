from a2a.server.apps import A2AStarletteApplication
from a2a.types import AgentCard, AgentCapabilities, AgentSkill
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.request_handlers import DefaultRequestHandler
import os
import logging
from dotenv import load_dotenv
from platform_mcp_client.agent_executor import (
    PlatformAgentExecutor,  
    PlatformAgent,
)
import uvicorn

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

host=os.environ.get("A2A_HOST", "localhost")
port=int(os.environ.get("A2A_PORT",10002))
PUBLIC_URL=os.environ.get("PUBLIC_URL")

if __name__ == '__main__':
    try:
        capabilities = AgentCapabilities(streaming=True)
        skill = AgentSkill(
            id="instavibe_posting",
            name="Post social post and events on instavibe",
            description="""
            This "Instavibe" agent helps you create posts (identifying author, text, and sentiment – inferred if unspecified) and register
            for events (gathering name, date, attendee). It efficiently collects required information and utilizes dedicated tools
            to perform these actions on your behalf, ensuring a smooth sharing experience.
            """,
            tags=["instavibe"],
            examples=["Create a post for me, the post is about my cute cat and make it positive, and I'm Alice"],
        )
        agent_card = AgentCard(
            name="Instavibe Posting Agent",
            description="""
            This "Instavibe" agent helps you create posts (identifying author, text, and sentiment – inferred if unspecified) and register
            for events (gathering name, date, attendee). It efficiently collects required information and utilizes dedicated tools
            to perform these actions on your behalf, ensuring a smooth sharing experience.
            """,
            url=f"{PUBLIC_URL}",
            version="1.0.0",
            defaultInputModes=PlatformAgent.SUPPORTED_CONTENT_TYPES,
            defaultOutputModes=PlatformAgent.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[skill],
        )
        request_handler = DefaultRequestHandler(
            agent_executor=PlatformAgentExecutor(),
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
