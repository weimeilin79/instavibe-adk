import asyncio
import json
import os
import uuid
import nest_asyncio 

from typing import Any, AsyncIterator

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
log = logging.getLogger(__name__)
 

load_dotenv()

root_agent: LlmAgent | None = None

REMOTE_AGENT_ADDRESSES_STR = os.getenv("REMOTE_AGENT_ADDRESSES", "")
REMOTE_AGENT_ADDRESSES = [addr.strip() for addr in REMOTE_AGENT_ADDRESSES_STR.split(',') if addr.strip()]

log.info(f"Remote Agent Addresses: {REMOTE_AGENT_ADDRESSES}")

def convert_part(part: Part, tool_context: ToolContext):
    """Convert a part to text. Only text parts are supported."""
    if part.type == 'text':
        return part.text

    return f'Unknown type: {part.type}'


def convert_parts(parts: list[Part], tool_context: ToolContext):
    """Convert parts to text."""
    rval = []
    for p in parts:
        rval.append(convert_part(p, tool_context))
    return rval


def create_send_message_payload(
    text: str, task_id: str | None = None, context_id: str | None = None
) -> dict[str, Any]:
    """Helper function to create the payload for sending a task."""
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


class HostAgent:
  """The orchestrate agent.

  This is the agent responsible for choosing which remote agents to send
  tasks to and coordinate their work.
  """

  def __init__(
        self,
        task_callback: TaskUpdateCallback | None = None,
    ):
        self.task_callback = task_callback
        self.remote_agent_connections: dict[str, RemoteAgentConnections] = {}
        self.cards: dict[str, AgentCard] = {}
        self.agents: str = ''

  async def _async_init_components(
        self, remote_agent_addresses: list[str]
    ) -> None:
        """Asynchronous part of initialization."""
        # Use a single httpx.AsyncClient for all card resolutions for efficiency
        async with httpx.AsyncClient(timeout=30) as client:
            for address in remote_agent_addresses:
                card_resolver = A2ACardResolver(
                    client, address
                )  # Constructor is sync
                try:
                    card = (
                        await card_resolver.get_agent_card()
                    )  # get_agent_card is async

                    remote_connection = RemoteAgentConnections(
                        agent_card=card, agent_url=address
                    )
                    self.remote_agent_connections[card.name] = remote_connection
                    self.cards[card.name] = card
                except httpx.ConnectError as e:
                    print(
                        f'ERROR: Failed to get agent card from {address}: {e}'
                    )
                except Exception as e:  # Catch other potential errors
                    print(
                        f'ERROR: Failed to initialize connection for {address}: {e}'
                    )

        # Populate self.agents using the logic from original __init__ (via list_remote_agents)
        agent_info = []
        for agent_detail_dict in self.list_remote_agents():
            agent_info.append(json.dumps(agent_detail_dict))
        self.agents = '\n'.join(agent_info)

  @classmethod
  async def create(
        cls,
        remote_agent_addresses: list[str],
        task_callback: TaskUpdateCallback | None = None,
    ) -> 'HostAgent':
        """Create and asynchronously initialize an instance of the HostAgent."""
        instance = cls(task_callback)
        await instance._async_init_components(remote_agent_addresses)
        return instance

  def create_agent(self) -> Agent:
        """Create an instance of the HostAgent."""
        return Agent(
            model="gemini-2.0-flash-001",
            name="orchestrate_agent",
            instruction=self.root_instruction,
            before_model_callback=self.before_model_callback,
            description=(
                "This agent orchestrates the decomposition of the user request into"
                " tasks that can be performed by the child agents."
            ),
            tools=[
                self.send_message,
            ],
        )

  def root_instruction(self, context: ReadonlyContext) -> str:
    current_agent = self.check_active_agent(context)
    return f"""

    You are an expert AI Orchestrator. Your primary responsibility is to intelligently interpret user requests, plan the necessary sequence of actions if multiple steps are involved, and delegate them to the most appropriate specialized remote agents using the `send_message` function. You do not perform the tasks yourself but manage their assignment, sequence, and can monitor their status.

        **Core Directives & Decision Making:**

        *   **Understand User Intent & Complexity:**
            *   Carefully analyze the user's request to determine the core task(s) they want to achieve. Pay close attention to keywords and the overall goal.
            *   Identify if the request requires a single agent or a sequence of actions from multiple agents. For example, "Analyze John Doe's profile and then create a positive post about his recent event attendance" would require two agents in sequence.

        *   **Task Planning & Sequencing (for Multi-Step Requests):**
            *   Before delegating, outline the clear sequence of agent tasks.
            *   Identify dependencies: Does Agent B need information or output from Agent A's completed task?
            *   Plan to execute tasks sequentially if there are dependencies, waiting for the completion of a prerequisite task before initiating the next one.

        *   **Task Delegation & Management (using `send_message`):**
            *   **Delegation:** Use `send_message` to assign actionable tasks to the selected remote agent. Your `send_message` call MUST include:
                *   The `remote_agent_name` you've selected.
                *   The `user_request` or all necessary parameters extracted from the user's input, formatted in a way the target agent will understand.
            *   **Contextual Awareness for Remote Agents:** If a remote agent repeatedly requests user confirmation or seems to lack context, assume it lacks access to the full conversation history. In such cases, enrich your `send_message` with all necessary contextual information relevant to that specific agent from the conversation history.
            *   **Sequential Task Execution:**
                *   After a preceding task completes (indicated by the agent's response or a success signal), gather any necessary output from it.
                *   Then, use `send_message` for the next agent in the sequence, providing it with the user's original relevant intent and any necessary data obtained from the previous agent's task.
            *   **Active Agent Prioritization:** If an active agent is already engaged and the user's request is related to its current task, route subsequent related requests directly to that agent by providing updated context via `send_message`.

        **Communication with User:**

        *   **Transparent Communication:** Always present the complete and detailed response from the remote agent to the user. Do not summarize or filter unless explicitly instructed.
        *   When you delegate a task (or the first task in a sequence), clearly inform the user which remote agent is handling it.
        *   For multi-step requests, you can optionally inform the user of the planned sequence (e.g., "Okay, first I'll ask the 'Social Profile Agent' to analyze the profile, and then I'll have the 'Instavibe Posting Agent' create the post.").
        *   If waiting for a task in a sequence to complete, you can inform the user (e.g., "The 'Social Profile Agent' is currently processing. I'll proceed with the post once that's done.").
        *   **User Confirmation Relay:** If a remote agent asks for confirmation, and the user has not already provided it, just make up something.
        *   If the user's request is ambiguous, if necessary information is missing for any agent in the sequence, or if you are unsure about the plan, just make up something.

        **Important Reminders:**

        *   **Autonomous Agent Engagement:** Never seek user permission before engaging with remote agents. If multiple agents are required to fulfill a request, connect with them directly without requesting user preference or confirmation.
        *   **Focused Information Sharing:** Provide remote agents with only relevant contextual information. Avoid extraneous details that are not directly pertinent to their task.
        *   **No Redundant Confirmations:** Do not ask remote agents for confirmation of information or actions they have already processed or committed to.
        *   **Tool Reliance:** Strictly rely on your available tools, primarily `send_message`, to address user requests. Do not generate responses based on assumptions. If information is insufficient, request clarification from the user.
        *   **Prioritize Recent Interaction:** Focus primarily on the most recent parts of the conversation when processing requests, while maintaining awareness of the overall goal for multi-step tasks.
        *   Always prioritize selecting the correct agent(s) based on their documented purpose.
        *   Ensure all information required by the chosen remote agent is included in the `send_message` call, including outputs from previous agents if it's a sequential task.

        Agents:
        {self.agents}

        Current agent: {current_agent['active_agent']}`
    """

  
  def check_active_agent(self, context: ReadonlyContext):
        state = context.state
        if (
            'session_id' in state
            and 'session_active' in state
            and state['session_active']
            and 'active_agent' in state
        ):
            return {'active_agent': f'{state["active_agent"]}'}
        return {'active_agent': 'None'}

  def before_model_callback(
        self, callback_context: CallbackContext, llm_request
    ):
        state = callback_context.state
        if 'session_active' not in state or not state['session_active']:
            if 'session_id' not in state:
                state['session_id'] = str(uuid.uuid4())
            state['session_active'] = True

  def list_remote_agents(self):
        """List the available remote agents you can use to delegate the task."""
        if not self.cards:
            return []

        remote_agent_info = []
        for card in self.cards.values():
            print(f'Found agent card: {card.model_dump(exclude_none=True)}')
            print('=' * 100)
            remote_agent_info.append(
                {'name': card.name, 'description': card.description}
            )
        return remote_agent_info

  async def send_message(
        self, agent_name: str, task: str, tool_context: ToolContext
    ):
        """Sends a task to remote seller agent.

        This will send a message to the remote agent named agent_name.

        Args:
            agent_name: The name of the agent to send the task to.
            task: The comprehensive conversation context summary
                and goal to be achieved regarding user inquiry and purchase request.
            tool_context: The tool context this method runs in.

        Yields:
            A dictionary of JSON data.
        """
        if agent_name not in self.remote_agent_connections:
            raise ValueError(f'Agent {agent_name} not found')
        state = tool_context.state
        state['active_agent'] = agent_name
        client = self.remote_agent_connections[agent_name]

        if not client:
            raise ValueError(f'Client not available for {agent_name}')
        task_id = state['task_id'] if 'task_id' in state else str(uuid.uuid4())

        if 'context_id' in state:
            context_id = state['context_id']
        else:
            context_id = str(uuid.uuid4())

        message_id = ''
        metadata = {}
        if 'input_message_metadata' in state:
            metadata.update(**state['input_message_metadata'])
            if 'message_id' in state['input_message_metadata']:
                message_id = state['input_message_metadata']['message_id']
        if not message_id:
            message_id = str(uuid.uuid4())

        payload = {
            'message': {
                'role': 'user',
                'parts': [
                    {'type': 'text', 'text': task}
                ],  # Use the 'task' argument here
                'messageId': message_id,
            },
        }

        if task_id:
            payload['message']['taskId'] = task_id

        if context_id:
            payload['message']['contextId'] = context_id

        message_request = SendMessageRequest(
            id=message_id, params=MessageSendParams.model_validate(payload)
        )
        send_response: SendMessageResponse = await client.send_message(
            message_request=message_request
        )
        print('send_response', send_response.model_dump_json(exclude_none=True, indent=2))

        if not isinstance(send_response.root, SendMessageSuccessResponse):
            print('received non-success response. Aborting get task ')
            return

        if not isinstance(send_response.root.result, Task):
            print('received non-task response. Aborting get task ')
            return

        return send_response.root.result




async def initialize():
   """Initializes the global root_agent and exit_stack."""
   global root_agent
   if root_agent is None:
       log.info("Initializing agent...")
       host_agent_instance = await HostAgent.create(REMOTE_AGENT_ADDRESSES)
       root_agent = host_agent_instance.create_agent()
       if root_agent:
           log.info("Agent initialized successfully.")
       else:
           log.error("Agent initialization failed.")
       
   else:
       log.info("Agent already initialized.")

def _cleanup_sync():
    """Synchronous wrapper to attempt async cleanup."""
    log.info("MCP connection cleanup is now handled externally.")
    # No specific cleanup action needed here as exit_stack is managed elsewhere.
    pass 


nest_asyncio.apply()

log.info("Running agent initialization at module level using asyncio.run()...")
try:
    asyncio.run(initialize())
    log.info("Module level asyncio.run(initialize()) completed.")
except RuntimeError as e:
    log.error(f"RuntimeError during module level initialization (likely nested loops): {e}", exc_info=True)
except Exception as e:
    log.error(f"Unexpected error during module level initialization: {e}", exc_info=True)

