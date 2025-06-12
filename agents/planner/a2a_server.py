from a2a.server.apps import A2AStarletteApplication
from a2a.types import AgentCard, AgentCapabilities, AgentSkill
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.request_handlers import DefaultRequestHandler
import os
import logging
from dotenv import load_dotenv
from planner.agent_executor import (
    PlannerAgentExecutor,  
    PlannerAgent,
)
import uvicorn

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

host=os.environ.get("A2A_HOST", "localhost")
port=int(os.environ.get("A2A_PORT",10003))
PUBLIC_URL=os.environ.get("PUBLIC_URL")

if __name__ == '__main__':
    try:
        capabilities = AgentCapabilities(streaming=True)
        skill = AgentSkill(
            id="night_out_planner",
            name="Night out planner",
            description="""
            This agent generates multiple fun plan suggestions tailored to your specified location, dates, and interests,
            all designed for a moderate budget. It delivers detailed itineraries,
            including precise venue information (name, latitude, longitude, and description), in a structured JSON format.
            """,
            tags=["instavibe"],
            examples=["What about Bostona MA this weekend?"],
        )
        agent_card = AgentCard(
            name="NightOut Planner Agent",
            description="""
            This agent generates multiple fun plan suggestions tailored to your specified location, dates, and interests,
            all designed for a moderate budget. It delivers detailed itineraries,
            including precise venue information (name, latitude, longitude, and description), in a structured JSON format.
            """,
            url=f"{PUBLIC_URL}",
            version="1.0.0",
            defaultInputModes=PlannerAgent.SUPPORTED_CONTENT_TYPES,
            defaultOutputModes=PlannerAgent.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[skill],
        )

        request_handler = DefaultRequestHandler(
            agent_executor=PlannerAgentExecutor(),
            task_store=InMemoryTaskStore(),
        )

        server = A2AStarletteApplication(
            agent_card=agent_card,
            http_handler=request_handler,
        )
        logger.info(f"Attempting to start server with Agent Card: {agent_card.name}")
        logger.info(f"Server object created: {server}")

        uvicorn.run(server.build(), host='0.0.0.0', port=port)
    except Exception as e:
        logger.error(f"An error occurred during server startup: {e}")
        exit(1)

