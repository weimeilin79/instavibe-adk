import datetime
from zoneinfo import ZoneInfo
from google.adk.agents import LoopAgent, LlmAgent, BaseAgent
from social.instavibe import get_person_posts,get_person_friends,get_person_id_by_name,get_person_attended_events
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from typing import AsyncGenerator
import logging

from google.genai import types # For types.Content
from google.adk.agents.callback_context import CallbackContext
from typing import Optional

# Get a logger instance
log = logging.getLogger(__name__)

class CheckCondition(BaseAgent): 
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        #log.info(f"Checking status: {ctx.session.state.get("summary_status", "fail")}")
        log.info(f"Summary: {ctx.session.state.get("summary")}")
        
        status = ctx.session.state.get("summary_status", "fail").strip() 
        is_done = (status == "completed") 
                
        #log.info(f"Checking is_done status: {is_done}")
        #log.info(f"Parts: {ctx.user_content.parts[0].text}")
        yield Event(author=self.name, actions=EventActions(escalate=is_done)) 


def modify_output_after_agent(callback_context: CallbackContext) -> Optional[types.Content]:

    agent_name = callback_context.agent_name
    invocation_id = callback_context.invocation_id
    current_state = callback_context.state.to_dict()
    current_user_content = callback_context.user_content
    print(f"[Callback] Exiting agent: {agent_name} (Inv: {invocation_id})")
    print(f"[Callback] Current summary_status: {current_state.get("summary_status")}")
    print(f"[Callback] Current Content: {current_user_content}")
    
    status = current_state.get("summary_status").strip() 
    is_done = (status == "completed") 
    # Retrieve the final summary from the state
    
    final_summary = current_state.get("summary")
    print(f"[Callback] final_summary: {final_summary}")
    if final_summary and is_done and isinstance(final_summary, str):
        log.info(f"[Callback] Found final summary, constructing output Content.")
        # Construct the final output Content object to be sent back
        return types.Content(role="model", parts=[types.Part(text=final_summary.strip())])
    else:
        log.warning("[Callback] No final summary found in state or it's not a string.")
        # Optionally return a default message or None if no summary was generated
        return None
    

profile_agent = LlmAgent(
    name="profile_agent",
    model="gemini-2.0-flash",
    description=(
        "Agent to answer questions about the this person's social profile. User will ask person's profile using their name, make sure to fetch the id before getting other data."
    ),
    instruction=(
        "You are a helpful agent who can answer user questions about this person's social profile."
    ),
    tools=[get_person_posts,get_person_friends,get_person_id_by_name,get_person_attended_events],
)

summary_agent = LlmAgent(
    name="summary_agent",
    model="gemini-2.0-flash",
    description=(
        "Summarize everyone's social profile on events, post and friends and at the end summarize into a paragraph and find the common ground between them."
    ),
    instruction=(
        "Base on the social profile data make sure you find the posts, friends, events they participated "
        "Summarize this data into a paragraph, finding common ground if multiple profiles are present."
        ),
    output_key="summary"
)


check_agent = LlmAgent(
    name="check_agent",
    model="gemini-2.0-flash",
    description=(
        "Check if everyone's social profile are summarized and has been generated. Output 'completed' or 'pending'."
    ),
    output_key="summary_status"
)

root_agent = LoopAgent(
    name="InterativePipeline",
    sub_agents=[
        profile_agent,
        summary_agent, 
        check_agent,
        CheckCondition(name="Checker")
    ],
    description="Find everyone's social profile on events, post and friends",
    max_iterations=10,
    after_agent_callback=modify_output_after_agent 
)