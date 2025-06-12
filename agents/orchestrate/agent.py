from orchestrate.host_agent import HostAgent
import asyncio
import os # Import os to read environment variables
from dotenv import load_dotenv
from google.genai import types
from google.adk.agents import BaseAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, SseServerParams
import logging 
import nest_asyncio # Import nest_asyncio
import atexit
from google.adk import Agent

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
 
# --- Global variables ---
# Define them first, initialize as None

# --- Configuration ---
# It's better to get this from environment variables or a config file
# Defaulting to empty list if not set. Adjust as needed.
REMOTE_AGENT_ADDRESSES_STR = os.getenv("REMOTE_AGENT_ADDRESSES", "")
log.info(f"Remote Agent Addresses String: {REMOTE_AGENT_ADDRESSES_STR}")
REMOTE_AGENT_ADDRESSES = [addr.strip() for addr in REMOTE_AGENT_ADDRESSES_STR.split(',') if addr.strip()]
log.info(f"Remote Agent Addresses: {REMOTE_AGENT_ADDRESSES}")

# --- Agent Initialization ---
# Instantiate the HostAgent logic class
# You might want to add a task_callback here if needed, similar to run_orchestrator.py


async def get_initialized_orchestrate_agent() -> Agent:
    """Asynchronously creates and initializes the OrchestrateAgent."""
    host_agent_logic = await HostAgent.create(REMOTE_AGENT_ADDRESSES)
    return host_agent_logic.create_agent()


root_agent = get_initialized_orchestrate_agent()
