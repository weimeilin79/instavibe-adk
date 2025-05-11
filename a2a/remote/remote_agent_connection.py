import sys # Import sys for stderr
import uuid
from typing import Callable, Optional # Import Optional
from common.types import (
    AgentCard,
    Task,
    TaskSendParams,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    TaskStatus,
    TaskState,
)
from common.client import A2AClient
import logging 
log = logging.getLogger(__name__)

TaskCallbackArg = Task | TaskStatusUpdateEvent | TaskArtifactUpdateEvent
TaskUpdateCallback = Callable[[TaskCallbackArg, AgentCard], Task]

class RemoteAgentConnections:
  """A class to hold the connections to the remote agents."""

  def __init__(self, agent_card: AgentCard):
    self.agent_client = A2AClient(agent_card)
    self.card = agent_card

    self.conversation_name = None
    self.conversation = None
    self.pending_tasks = set()

  def get_agent(self) -> AgentCard:
    return self.card

  async def send_task(
      self,
      request: TaskSendParams,
      task_callback: TaskUpdateCallback | None,
  ) -> Task | None:
    final_task_object: Optional[Task] = None # Store the definitive final Task object if received
    # Store the last status update event *that had a message*
    last_status_update_with_message: Optional[TaskStatusUpdateEvent] = None

    if self.card.capabilities.streaming:
      # --- Initial Submitted State ---
      if task_callback:
        # Call initial callback for SUBMITTED state
        task_callback(Task(
            id=request.id,
            sessionId=request.sessionId,
            status=TaskStatus(
                state=TaskState.SUBMITTED,
                message=request.message,
            ),
            history=[request.message],
        ), self.card)

      # --- Streaming Updates ---
      async for response in self.agent_client.send_task_streaming(request.model_dump()):
        merge_metadata(response.result, request)
        # For task status updates, we need to propagate metadata and provide
        # a unique message id.
        if (hasattr(response.result, 'status') and
            hasattr(response.result.status, 'message') and
            response.result.status.message):
          merge_metadata(response.result.status.message, request.message)
          m = response.result.status.message
          if not m.metadata:
            m.metadata = {}
          if 'message_id' in m.metadata:
            m.metadata['last_message_id'] = m.metadata['message_id']
          m.metadata['message_id'] = str(uuid.uuid4())

        current_update = response.result

        # Call the callback for notification, ignore its return value here
        if task_callback:
          try:
              task_callback(response.result, self.card)
          except Exception as e:
              # Log callback errors but don't let them stop the main flow
              print(f"Error in task callback during streaming: {e}", file=sys.stderr)

        # Store the last status update event *with a message*
        if isinstance(current_update, TaskStatusUpdateEvent) and current_update.status and current_update.status.message:
            log.debug(f"Storing last_status_update_with_message: {current_update.id}") # Added debug log
            last_status_update_with_message = current_update

        # Check if this update is the definitive final Task object
        if isinstance(current_update, Task) and current_update.status and current_update.status.state in [TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELED]:
             final_task_object = current_update # Store the final task object

        # Stop if the final flag is set
        if hasattr(current_update, 'final') and current_update.final:
          break

    else: # Non-streaming
      response = await self.agent_client.send_task(request.model_dump())
      merge_metadata(response.result, request)
      # For task status updates, we need to propagate metadata and provide
      # a unique message id.
      if (hasattr(response.result, 'status') and
          hasattr(response.result.status, 'message') and
          response.result.status.message):
        merge_metadata(response.result.status.message, request.message)
        m = response.result.status.message
        if not m.metadata:
          m.metadata = {}
        if 'message_id' in m.metadata:
          m.metadata['last_message_id'] = m.metadata['message_id']
        m.metadata['message_id'] = str(uuid.uuid4())

      current_update = response.result

      # Store the final result from the non-streaming call
      if isinstance(current_update, Task):
          final_task_object = current_update

      # Store the last status update event *with a message*
      if isinstance(current_update, TaskStatusUpdateEvent) and current_update.status and current_update.status.message:
          last_status_update_with_message = current_update
      # Call the callback for notification, ignore its return value
      if task_callback:
        try:
            task_callback(response.result, self.card)
        except Exception as e:
            print(f"Error in task callback during non-streaming: {e}", file=sys.stderr)

    # --- Determine Return Value ---
    # Prioritize returning the definitive Task object if we received one
    if final_task_object:
        log.info(f"Returning definitive final_task_object: {final_task_object}")
        return final_task_object

    # If no definitive Task object, but we have a final status update *with a message*, construct a Task from it
    if last_status_update_with_message:
        log.info(f"Constructing Task from last_status_update_with_message: {last_status_update_with_message}")
        return Task(
            id=last_status_update_with_message.id,
            sessionId=request.sessionId, # Get sessionId from original request
            status=last_status_update_with_message.status,
            # Note: history and artifacts might be missing or incomplete here
        )

    # If neither a full Task nor a final status update was found, return None
    log.warning("No definitive Task or last status update found. Returning None.")
    return None


def merge_metadata(target, source):
  if not hasattr(target, 'metadata') or not hasattr(source, 'metadata'):
    return
  if target.metadata and source.metadata:
    target.metadata.update(source.metadata)
  elif source.metadata:
    target.metadata = dict(**source.metadata)
