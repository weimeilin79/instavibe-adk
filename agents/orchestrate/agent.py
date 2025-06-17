import asyncio
import json
import os
import uuid
from typing import Any

import httpx

from a2a.client import A2ACardResolver
from a2a.types import (
    AgentCard,
    MessageSendParams,
    Part,
    SendMessageRequest,
    SendMessageResponse,
    SendMessageSuccessResponse,
    Task,
    TaskState,
)
try:
    from remote_agent_connection import (
        RemoteAgentConnections,
        TaskUpdateCallback,
    )
except ImportError:
    from orchestrate.remote_agent_connection import (
        RemoteAgentConnections,
        TaskUpdateCallback,
    )
from dotenv import load_dotenv
from google.adk import Agent
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.tool_context import ToolContext
import logging

# Set up logging to INFO, but we will use ERROR for diagnostics
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# --- Configuration ---
REMOTE_AGENT_ADDRESSES_STR = os.getenv("REMOTE_AGENT_ADDRESSES", "")
REMOTE_AGENT_ADDRESSES = [addr.strip() for addr in REMOTE_AGENT_ADDRESSES_STR.split(',') if addr.strip()]

log.info(f"Remote Agent Addresses: {REMOTE_AGENT_ADDRESSES}")

# --- Helper Functions (Unchanged) ---
def create_send_message_payload(
    text: str, task_id: str | None = None, context_id: str | None = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'message': {
            'role': 'user',
            'parts': [{'type': 'text', 'text': text}],
            'messageId': uuid.uuid4().hex,
        },
    }
    if task_id:
        payload['message']['taskId'] = task_id
    if context_id:
        payload['message']['contextId'] = context_id
    return payload


# --- Main Agent Class ---
class HostAgent:
    """The orchestrate agent with a special diagnostic initializer."""

    def __init__(self, task_callback: TaskUpdateCallback | None = None):
        log.info("HostAgent instance created in memory (uninitialized).")
        self.task_callback = task_callback
        self.remote_agent_connections: dict[str, RemoteAgentConnections] = {}
        self.cards: dict[str, AgentCard] = {}
        self.agents: str = ''
        self.is_initialized = False

    async def _initialize(self):
        """
        DIAGNOSTIC VERSION: This method will test each connection one-by-one
        with aggressive logging to force the hidden error to appear.
        """
        
        log.info(f"STEP 1: The following addresses will be tested: {REMOTE_AGENT_ADDRESSES}")
        if not REMOTE_AGENT_ADDRESSES or not REMOTE_AGENT_ADDRESSES[0]:
            log.info("CRITICAL FAILURE: REMOTE_AGENT_ADDRESSES environment variable is empty. Cannot proceed.")
            # Set as initialized to prevent this from running again, but the agent will fail.
            self.is_initialized = True
            return

        async with httpx.AsyncClient(timeout=45) as client:
            

            for i, address in enumerate(REMOTE_AGENT_ADDRESSES):
                log.info(f"--- STEP 3.{i}: Attempting connection to: {address} ---")
                try:
                    card_resolver = A2ACardResolver(client, address)
                    card = await card_resolver.get_agent_card()
                    log.info(f"--- STEP 4.{i}: SUCCESS for {address}. Agent name: {card.name} ---")
                    
                    remote_connection = RemoteAgentConnections(agent_card=card, agent_url=address)
                    self.remote_agent_connections[card.name] = remote_connection
                    self.cards[card.name] = card
                    log.info(f"--- STEP 5.{i}: Successfully stored connection for {card.name} ---")

                except Exception as e:
                    # This is the most important log. We force it to appear.
                    log.error(f"--- CRITICAL FAILURE at STEP 4.{i} for address: {address} ---")
                    log.error(f"--- The hidden exception type is: {type(e).__name__} ---")
                    log.error(f"--- Full exception details and traceback: ---", exc_info=True)
                    # Continue to the next address to see if others work.
        
        log.error("STEP 6: Finished attempting all connections.")
        if not self.remote_agent_connections:
            log.error("FINAL VERDICT: The loop finished, but the remote agent list is still empty.")
            # We don't raise an error here, to allow the agent to run and show the empty list.
        else:
            agent_info = [json.dumps({'name': c.name, 'description': c.description}) for c in self.cards.values()]
            self.agents = '\n'.join(agent_info)
            log.info(f"--- FINAL SUCCESS: Initialization complete. {len(self.remote_agent_connections)} agents loaded. ---")
        
        # Mark as initialized regardless of success to prevent re-runs.
        self.is_initialized = True

    async def before_agent_callback(self, callback_context: CallbackContext):
        """The trigger for our lazy initialization."""
        log.info("`before_agent_callback` triggered.")
        if not self.is_initialized:
            await self._initialize()

    def root_instruction(self, context: ReadonlyContext) -> str:
        """Provides the main instruction prompt."""
        return f"""
        You are an expert AI Orchestrator. You must delegate tasks to the agents below.

        **Available Agents:**
        {self.agents}
        """

    async def send_message(self, agent_name: str, task: str, tool_context: ToolContext):
        """Sends a task to a remote agent."""
        if agent_name not in self.remote_agent_connections:
            log.error(f"LLM tried to call '{agent_name}' but it was not found. Available agents: {list(self.remote_agent_connections.keys())}")
            raise ValueError(f"Agent '{agent_name}' not found.")
        
        client = self.remote_agent_connections[agent_name]
        payload = create_send_message_payload(task)
        message_request = SendMessageRequest(id=str(uuid.uuid4()), params=MessageSendParams.model_validate(payload))
        return await client.send_message(message_request=message_request)

    def create_agent(self) -> Agent:
        """Synchronously creates the ADK Agent object."""
        return Agent(
            model="gemini-2.0-flash-001",
            name="orchestrate_agent",
            instruction=self.root_instruction,
            before_agent_callback=self.before_agent_callback,
            description=("Orchestrates tasks for child agents."),
            tools=[self.send_message],
        )

# --- Top-Level Execution ---

log.info("Module-level code is running. Creating uninitialized agent object...")
host_agent_singleton = HostAgent()
root_agent = host_agent_singleton.create_agent()
log.info("Module-level setup finished. 'root_agent' is populated.")
