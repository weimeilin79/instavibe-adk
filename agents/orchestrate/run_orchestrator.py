# run_orchestrator.py
import asyncio
import sys
from google.genai import types
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService # Added import

# Assuming your project structure allows this import path
from orchestrate.host_agent import HostAgent 
# Import specific types needed for isinstance checks
from common.types import (
    AgentCard,
    Task,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent, # Assuming this type exists in common.types
    TextPart # Needed for message printing
)
from remote.remote_agent_connection import TaskUpdateCallback, TaskCallbackArg

from dotenv import load_dotenv

load_dotenv()



# --- Configuration ---
REMOTE_AGENT_ADDRESSES = [
    "https://social-agent-service-789872749985.us-central1.run.app", 
    "https://planner-agent-service-789872749985.us-central1.run.app", 
    "https://platform-mcp-client-789872749985.us-central1.run.app",
]
USER_ID = "orchestrator_user"
APP_NAME = "datecoach_orchestrator"
# --- End Configuration ---

# Simple callback to print task updates (optional)
def print_task_update(update: TaskCallbackArg, agent_card: AgentCard):
    """Prints updates received from remote agents."""
    
    task = None
    # Check for event types first using the more specific 'taskId' attribute
    # Use isinstance for reliable type checking
    if isinstance(update, TaskStatusUpdateEvent): # Check if it's a TaskStatusUpdateEvent or TaskArtifactUpdateEvent
        print(f"--- Event Update [{agent_card.name}] ---")
        # Use 'id' as confirmed by previous debug output and current error
        print(f"  Task ID: {update.id}")
        print(f"  Status: {update.status.state.value}")
        if update.status.message and update.status.message.parts:
             # Assuming the first part is TextPart
             if isinstance(update.status.message.parts[0], TextPart):
                 print(f"  Message: {update.status.message.parts[0].text}")
             else:
                 print(f"  Message: (Non-text part)")
        else:
             print(f"  Message: N/A")
        print("----------------------------------")
    elif isinstance(update, TaskArtifactUpdateEvent):
        print(f"--- Event Artifact Update [{agent_card.name}] ---")
        # Assuming TaskArtifactUpdateEvent also uses 'id'
        print(f"  Task ID: {update.id}")
        if hasattr(update, 'artifact'): # Check artifact exists
             print(f"  Artifact Added: {update.artifact.index} ({len(update.artifact.parts)} parts)")
        print("----------------------------------")
    elif isinstance(update, Task): # Check if it's a full Task object
        task = update # Assign to task variable only if it's a Task object
        print(f"--- Task Update [{agent_card.name}] ---")
        print(f"  Task ID: {task.id}")
        print(f"  Status: {task.status.state.value}")
        if task.status.message:
            print(f"  Message: {task.status.message.parts[0].text if task.status.message.parts else 'N/A'}")
        # !!! This is the likely point of failure if the object is actually an event !!!
        if hasattr(task, 'artifacts') and task.artifacts: # Safely check for artifacts
             print(f"  Artifacts: {len(task.artifacts)}")
        else:
             print(f"  Artifacts: (Attribute not found or empty)") # Add else for clarity
        print("---------------------------------")
    else:
        print(f"--- Unknown Update Type [{agent_card.name}] ---")
        # Print details even for unknown types
        print(f"  Update Type: {type(update)}")
        print(f"  Update Data: {update}")
        print("---------------------------------------")

    # The callback in HostAgent expects the updated Task to be returned
    # This simple print callback doesn't modify the task, so we find/return it
    # A more complex callback might update task state based on events
    if task:
        return task
    # If it was an event, we don't have the full task object here easily
    # The HostAgent's send_task handles the final task return value
    return None


async def async_main():
    """Runs the orchestrator agent interactively."""
    print("Initializing Orchestrator Host Agent...")
    print(f"Connecting to remote agents at: {', '.join(REMOTE_AGENT_ADDRESSES)}")

    # 1. Instantiate HostAgent with addresses and the callback
    orchestrator_agent_logic = HostAgent(
        remote_agent_addresses=REMOTE_AGENT_ADDRESSES,
        task_callback=print_task_update
    )

    # 2. Create the underlying ADK Agent
    orchestrator_agent = orchestrator_agent_logic.create_agent()
    print(f"Orchestrator Agent '{orchestrator_agent.name}' created.")

    # 3. Set up the ADK Runner
    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()
    memory_service = InMemoryMemoryService() # Added memory service

    runner = Runner(
        app_name=APP_NAME,
        agent=orchestrator_agent,
        artifact_service=artifact_service,
        session_service=session_service,
        memory_service=memory_service, # Pass memory service to Runner
    )

    # 4. Create a session
    session = session_service.create_session(
        state={}, app_name=APP_NAME, user_id=USER_ID
    )
    print(f"Session created: {session.id}")
    print("\nOrchestrator ready. Type your request (or 'quit' to exit).")

    # 5. Interactive loop
    while True:
        try:
            user_input = input("> ")
            if user_input.lower() == 'quit':
                break
            if not user_input:
                continue

            content = types.Content(role='user', parts=[types.Part(text=user_input)])

            print("... Sending request to orchestrator ...")
            events_async = runner.run_async(
                session_id=session.id, user_id=session.user_id, new_message=content
            )

            final_response_parts = []
            async for event in events_async:
                

                # Process content if the event has it, even if not explicitly 'agent:final_turn'
                # This handles cases where the final response is in a generic Event object.
                if hasattr(event, 'content'):
                    content = event.content # We know it exists due to hasattr check
                    parts = content.parts if content and hasattr(content, 'parts') else []
                    for part in parts:
                        # Check if part is a google.genai.types.Part object with text
                        if hasattr(part, 'text') and isinstance(part.text, str):
                            final_response_parts.append(part.text)
                         # Keep checks for dicts potentially returned by convert_part
                        elif isinstance(part, dict) and 'data' in part:
                             final_response_parts.append(f"[Data Artifact: {part['data']}]")
                        elif isinstance(part, str): # Direct string output
                             final_response_parts.append(part)


            print("\n--- Orchestrator Response ---")
            if final_response_parts:
                print("\n".join(final_response_parts))
            else:
                print("(No text response received)")
            print("---------------------------\n")


        except Exception as e:
            print(f"\nAn error occurred: {e}", file=sys.stderr)
            # Optionally break the loop on error or continue
            # break

    print("Exiting orchestrator.")


if __name__ == "__main__":
    # Make sure the remote agents are running before starting this script!
    # e.g., python -m agents.social.a2a_server (in one terminal)
    #       python -m agents.planner.a2a_server (in another terminal)
    #       python -m agents.introvertally.a2a_server (in a third terminal)
    # Then run this script: python run_orchestrator.py
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\nCaught interrupt, exiting.")
