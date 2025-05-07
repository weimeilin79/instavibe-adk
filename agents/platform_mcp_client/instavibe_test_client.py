import asyncio
from dotenv import load_dotenv
from google.genai import types
from google.adk.agents.llm_agent import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService # Optional


from agent import get_agent_async
import asyncio

load_dotenv()


async def async_main():
  session_service = InMemorySessionService()
  # Artifact service might not be needed for this example
  artifacts_service = InMemoryArtifactService()

  session = session_service.create_session(
      state={}, app_name='mcp_instavibe_app', user_id='user_dc'
  )

  query = "Create an event for me, the event is going to movie night on Friday the movie is ET, and I'm Mike, I'll be the organizer and the date 2025/10/13 8:00pm EST"
  print(f"User Query: '{query}'")
  content = types.Content(role='user', parts=[types.Part(text=query)])

  root_agent, exit_stack = await get_agent_async()

  async with exit_stack:
      runner = Runner(
          app_name='mcp_instavibe_app',
          agent=root_agent,
          artifact_service=artifacts_service, # Optional
          session_service=session_service,
      )

      print("Running agent...")
      events_async = runner.run_async(
          session_id=session.id, user_id=session.user_id, new_message=content
      )

  async for event in events_async:
    print(f"Event received: {event}")
    # Crucial Cleanup: Ensure the MCP server process connection is closed.
    print("Closing MCP server connection...")
    await exit_stack.aclose()
    print("Cleanup complete.")

if __name__ == '__main__':
  try:
    asyncio.run(async_main())
  except Exception as e:
    print(f"An error occurred: {e}")