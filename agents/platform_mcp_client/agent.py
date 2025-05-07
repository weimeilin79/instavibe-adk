import asyncio
from contextlib import AsyncExitStack
from dotenv import load_dotenv
from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, SseServerParams
import logging 
import os
import nest_asyncio # Import nest_asyncio


# Load environment variables from .env file in the parent directory
# Place this near the top, before using env vars like API keys
load_dotenv()
MCP_SERVER_URL=os.environ.get("MCP_SERVER_URL", "http://0.0.0.0:8080/sse")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
 
# --- Global variables ---
# Define them first, initialize as None
root_agent: LlmAgent | None = None
exit_stack: AsyncExitStack | None = None


async def get_tools_async():
  """Gets tools from the File System MCP Server."""
  print("Attempting to connect to MCP Filesystem server...")
  tools, exit_stack = await MCPToolset.from_server(
      connection_params=SseServerParams(url=MCP_SERVER_URL, headers={})
  )
  log.info("MCP Toolset created successfully.")

  return tools, exit_stack
 

async def get_agent_async():
  """
  Asynchronously creates the MCP Toolset and the LlmAgent.

  Returns:
      tuple: (LlmAgent instance, AsyncExitStack instance for cleanup)
  """
  tools, exit_stack = await get_tools_async()

  root_agent = LlmAgent(
      model='gemini-2.0-flash', # Adjust model name if needed based on availability
      name='social_agent',
      instruction='Help user interact with the social app Instavibe using available tools.',
      tools=tools,
  )
  print("LlmAgent created.")

  # Return both the agent and the exit_stack needed for cleanup
  return root_agent, exit_stack


async def initialize():
   """Initializes the global root_agent and exit_stack."""
   global root_agent, exit_stack
   if root_agent is None:
       log.info("Initializing agent...")
       root_agent, exit_stack = await get_agent_async()
       if root_agent:
           log.info("Agent initialized successfully.")
       else:
           log.error("Agent initialization failed.")
       
   else:
       log.info("Agent already initialized.")

def _cleanup_sync():
    """Synchronous wrapper to attempt async cleanup."""
    if exit_stack:
        log.info("Attempting to close MCP connection via atexit...")
        try:
            asyncio.run(exit_stack.aclose())
            log.info("MCP connection closed via atexit.")
        except Exception as e:
            log.error(f"Error during atexit cleanup: {e}", exc_info=True)


nest_asyncio.apply()

log.info("Running agent initialization at module level using asyncio.run()...")
try:
    asyncio.run(initialize())
    log.info("Module level asyncio.run(initialize()) completed.")
except RuntimeError as e:
    log.error(f"RuntimeError during module level initialization (likely nested loops): {e}", exc_info=True)
except Exception as e:
    log.error(f"Unexpected error during module level initialization: {e}", exc_info=True)

