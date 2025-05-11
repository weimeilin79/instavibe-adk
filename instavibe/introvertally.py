from vertexai import agent_engines
from dotenv import load_dotenv
import pprint
import json 
import os

load_dotenv()

ORCHESTRATE_AGENT_ID = os.environ.get('ORCHESTRATE_AGENT_ID',"projects/789872749985/locations/us-central1/reasoningEngines/7321524784058073088")

agent_engine = agent_engines.get(ORCHESTRATE_AGENT_ID)



def call_agent_for_plan(user_name, planned_date, location_n_perference, selected_friend_names_list):
    user_id = str(user_name)
    # agent_thoughts_log = [] # No longer needed here, we yield directly

    yield {"type": "thought", "data": f"--- IntrovertAlly Agent Call Initiated ---"}
    yield {"type": "thought", "data": f"Session ID for this run: {user_id}"}
    yield {"type": "thought", "data": f"User: {user_name}"}
    yield {"type": "thought", "data": f"Planned Date: {planned_date}"}
    yield {"type": "thought", "data": f"Location/Preference: {location_n_perference}"}
    yield {"type": "thought", "data": f"Selected Friends: {', '.join(selected_friend_names_list)}"}
    yield {"type": "thought", "data": f"Initiating plan for {user_name} on {planned_date} regarding '{location_n_perference}' with friends: {', '.join(selected_friend_names_list)}."}

    selected_friend_names_str = ', '.join(selected_friend_names_list)
    # print(f"Selected Friends (string for agent): {selected_friend_names_str}") # Console log

    # Constructing an example for the prompt, e.g., ["Alice", "Bob"]
    friends_list_example_for_prompt = json.dumps(selected_friend_names_list)

    prompt_message = f"""
    You are an expert event planner for a user named {user_name}.
    Your task is to design a fun and personalized night out.

    Here are the details for the plan:
    - Friends to invite: {selected_friend_names_str}
    - Desired date: {planned_date}
    - Location idea or general preference: "{location_n_perference}"

    Your process should be:
    1. Analyze the provided friend names. If you have access to a tool to get their Instavibe profiles or summarized interests, please use it.
    2. Based on their potential interests (or general good taste if profiles are unavailable), create a tailored plan for the outing.
    3. Ensure the plan includes the original `planned_date` provided: {planned_date}.
    4. Organize all details into a structured JSON format as specified below.

    The user wants a comprehensive plan that includes:
    - The list of invited friends.
    - A catchy and descriptive name for the event.
    - The exact planned date for the event (which is {planned_date}).
    - A summary of what the group will do.
    - Specific recommended spots (e.g., restaurants, bars, activity venues) with their names, (if possible, approximate latitude/longitude for mapping, and address), and a brief description of why it fits the plan.
    - A short, exciting message that {user_name} can send to {selected_friend_names_str} to get them excited about the event.

    IMPORTANT FINAL OUTPUT INSTRUCTION:
    After all necessary agent tasks in your plan are completed, your **final response to this entire request MUST be a single, complete JSON object**.
    This JSON object should strictly adhere to the following structure. You are responsible for gathering all information and constructing this JSON:

    {{
      "friends_name_list": {friends_list_example_for_prompt}, // This should be an array of strings, reflecting the names: {selected_friend_names_str}
      "event_name": "string",        // Synthesize a concise, descriptive name for the overall planned outing (e.g., "{selected_friend_names_str}'s Epic City Adventure")
      "event_date": "{planned_date}", // CRITICAL: Include the planned_date here in ISO 8601 format. This value is: {planned_date}
      "event_description": "string", // Provide an engaging summary of the planned activities and overall vibe of the event.
      "locations_and_activities": [  // This array should detail each step of the plan.
        {{
          "name": "string",          // Name of the specific place, venue, or activity.
          "latitude": 12.345,        // Approximate latitude (e.g., 34.0522) or null if not available.
          "longitude": -67.890,      // Approximate longitude (e.g., -118.2437) or null if not available.
          "address": "string or null", // Physical address if available, otherwise null.
          "description": "string"    // Brief description of this location/activity and why it's part of the plan.
        }}
        // Add more location/activity objects as needed for the plan.
      ],
      "post_to_go_out": "string"     // MUST generate a short, catchy, and exciting text message
                                   // that {user_name} can send to the friends to invite them and build anticipation.
                                   // Make it sound like it's from {user_name}.
    }}

    Your final response for this entire request MUST be ONLY the JSON object described above.
    Do NOT include any conversational text, explanations, or markdown formatting like ```json before or after the JSON object itself. Just the raw, valid JSON.
    """

    print(f"--- Sending Prompt to Agent ---") 
    print(prompt_message) 
    yield {"type": "thought", "data": f"Sending detailed planning prompt to agent for {user_name}'s event."}

    accumulated_json_str = ""

    yield {"type": "thought", "data": f"--- Agent Response Stream Starting ---"}
    try:
        for event_idx, event in enumerate(agent_engine.stream_query(
            user_id=user_id,
            message=prompt_message,
        )):
            print(f"\n--- Event {event_idx} Received ---") # Console
            pprint.pprint(event) # Console
            try:
                content = event.get('content', {})
                parts = content.get('parts', [])
                
                if not parts:
                    pass # Avoid too much noise for empty events
                for part_idx, part in enumerate(parts):
                    if isinstance(part, dict):
                        text = part.get('text')
                        if text:
                            yield {"type": "thought", "data": f"Agent: \"{text}\""}
                            accumulated_json_str += text
                        else:
                            tool_code = part.get('tool_code')
                            tool_code_output = part.get('tool_code_output')
                            if tool_code:
                                yield {"type": "thought", "data": f"Agent is considering using a tool: {tool_code.get('name', 'Unnamed tool')}."}
                            if tool_code_output:
                                yield {"type": "thought", "data": f"Agent received output from tool '{tool_code.get('name', 'Unnamed tool')}'."}
            except Exception as e_inner:
                yield {"type": "thought", "data": f"Error processing agent event part {event_idx}: {str(e_inner)}"}

    except Exception as e_outer:
        yield {"type": "thought", "data": f"Critical error during agent stream query: {str(e_outer)}"}
        yield {"type": "error", "data": {"message": f"Error during agent interaction: {str(e_outer)}", "raw_output": accumulated_json_str}}
        return # Stop generation
    
    yield {"type": "thought", "data": f"--- End of Agent Response Stream ---"}

    # Attempt to extract JSON if it's wrapped in markdown
    if "```json" in accumulated_json_str:
        print("Detected JSON in markdown code block. Extracting...") 
       
        try:
            # Extract content between ```json and ```
            json_block = accumulated_json_str.split("```json", 1)[1].rsplit("```", 1)[0].strip()
            accumulated_json_str = json_block
            print(f"Extracted JSON block: {accumulated_json_str}") 
        except IndexError:
            # print("Error extracting JSON from markdown block. Will try to parse as is.") # Console
            yield {"type": "thought", "data": "Could not extract JSON from markdown block, will attempt to parse the full response."}

    if accumulated_json_str:
        try:
            final_result_json = json.loads(accumulated_json_str)
            yield {"type": "plan_complete", "data": final_result_json}
        except json.JSONDecodeError as e:
            # print(f"Error decoding accumulated string as JSON: {e}") # Console
            yield {"type": "thought", "data": f"Failed to parse the agent's output as a valid plan. Error: {e}"}
            yield {"type": "thought", "data": f"Raw output received: {accumulated_json_str}"}
            # print("Returning raw accumulated string due to JSON parsing error.") # Console
            yield {"type": "error", "data": {"message": f"JSON parsing error: {e}", "raw_output": accumulated_json_str}}
    else:
        # print("No text content accumulated from agent response.") # Console
        yield {"type": "thought", "data": "Agent did not provide any text content in its response."}
        yield {"type": "error", "data": {"message": "Agent returned no content.", "raw_output": ""}}



def post_plan_event(user_name, confirmed_plan, edited_invite_message, agent_session_user_id):
    """
    Simulates an agent posting an event and a message to Instavibe.
    Yields 'thought' events for logging.
    """
    yield {"type": "thought", "data": f"--- Post Plan Event Agent Call Initiated ---"}
    yield {"type": "thought", "data": f"Agent Session ID for this run: {agent_session_user_id}"}
    yield {"type": "thought", "data": f"User performing action: {user_name}"}
    yield {"type": "thought", "data": f"Received Confirmed Plan (event_name): {confirmed_plan.get('event_name', 'N/A')}"}
    yield {"type": "thought", "data": f"Received Invite Message: {edited_invite_message[:100]}..."} # Log a preview
    yield {"type": "thought", "data": f"Initiating process to post event and invite for {user_name}."}

    prompt_message = f"""
    You are an Orchestrator assistant for the Instavibe platform. User '{user_name}' has finalized an event plan and wants to:
    1. Create the event on Instavibe.
    2. Create an invite post for this event on Instavibe.

    You have tools like `list_remote_agents` to discover available specialized agents and `send_task(agent_name: str, message: str)` to delegate tasks to them.
    Your primary role is to understand the user's overall goal, identify the necessary steps, select the most appropriate remote agent(s) for those steps, and then send them clear instructions.

    Confirmed Plan:
    ```json
    {json.dumps(confirmed_plan, indent=2)}
    ```

    Invite Message (this is the exact text for the post content):
    "{edited_invite_message}"

    Your explicit tasks are, in this exact order:

    TASK 1: Create the Event on Instavibe.
    - First, identify a suitable remote agent that is capable of creating events on the Instavibe platform. You should use your `list_remote_agents` tool if you need to refresh your knowledge of available agents and their capabilities.
    - Once you have selected an appropriate agent, you MUST use your tool to instruct that agent to create the event.
    - The `message` you send to the agent for this task should be a clear, natural language instruction. This message MUST include all necessary details for event creation, derived from the "Confirmed Plan" JSON:
        - Event Name: "{confirmed_plan.get('event_name', 'Unnamed Event')}"
        - Event Description: "{confirmed_plan.get('event_description', 'No description provided.')}"
        - Event Date: "{confirmed_plan.get('event_date', 'MISSING_EVENT_DATE_IN_PLAN')}" (ensure this is in a standard date/time format like ISO 8601)
        - Locations: {json.dumps(confirmed_plan.get('locations_and_activities', []))} (describe these locations clearly to the agent)
        - Attendees: {json.dumps(list(set(confirmed_plan.get('friends_name_list', []) + [user_name])))} (this list includes the user '{user_name}' and their friends)
    - Narrate your thought process: which agent you are selecting (or your criteria if you can't name it), and the natural language message you are formulating for the tool to create the event.
    - After the  tool call is complete, briefly acknowledge its success based on the tool's response.

    TASK 2: Create the Invite Post on Instavibe.
    - Only after TASK 1 (event creation) is confirmed as  successful, you MUST use your tool again.
    - The `message` you send to the agent for this task should be a clear, natural language instruction to create a post. This message MUST include:
        - The author of the post: "{user_name}"
        - The content of the post: The "Invite Message" provided above ("{edited_invite_message}")
        - An instruction to associate this post with the event created in TASK 1 (e.g., by referencing its name: "{confirmed_plan.get('event_name', 'Unnamed Event')}").
        - Indicate the sentiment is "positive" as it's an invitation.
    - Narrate the natural language message you are formulating for the `send_task` tool to create the post.
    - After the `send_task` tool call is (simulated as) complete, briefly acknowledge its success.

    IMPORTANT INSTRUCTIONS FOR YOUR BEHAVIOR:
    - Your primary role here is to orchestrate these two actions by selecting an appropriate remote agent and sending it clear, natural language instructions via your  tool.
    - Your responses during this process should be a stream of consciousness, primarily narrating your agent selection (if applicable), the formulation of your natural language messages for , and theiroutcomes.
    - Do NOT output any JSON yourself. Your output must be plain text only, describing your actions.
    - Conclude with a single, friendly success message confirming that you have (simulated) instructing the remote agent to create both the event and the post. For example: "Alright, I've instructed the appropriate Instavibe agent to create the event '{confirmed_plan.get('event_name', 'Unnamed Event')}' and to make the invite post for {user_name}!"

    """

    yield {"type": "thought", "data": f"Sending posting instructions to agent for {user_name}'s event."}
    print(f"prompt_message: {prompt_message}") 
    
    accumulated_response_text = ""

    try:
        for event_idx, event in enumerate(agent_engine.stream_query(
            user_id=agent_session_user_id, # Use the agent session ID
            message=prompt_message,
        )):
            print(f"\n--- Post Event - Agent Event {event_idx} Received ---") # Console
            pprint.pprint(event) # Console
            try:
                content = event.get('content', {})
                parts = content.get('parts', [])
                for part_idx, part in enumerate(parts):
                    if isinstance(part, dict):
                        text = part.get('text')
                        if text:
                            yield {"type": "thought", "data": f"Agent: \"{text}\""}
                            accumulated_response_text += text
                        # We don't expect tool calls here for this simulation
            except Exception as e_inner:
                yield {"type": "thought", "data": f"Error processing agent event part {event_idx} during posting: {str(e_inner)}"}

    except Exception as e_outer:
        yield {"type": "thought", "data": f"Critical error during agent stream query for posting: {str(e_outer)}"}
        yield {"type": "error", "data": {"message": f"Error during agent interaction for posting: {str(e_outer)}", "raw_output": accumulated_response_text}}
        return # Stop generation if there's a major error

    yield {"type": "thought", "data": f"--- End of Agent Response Stream for Posting ---"}
    yield {"type": "posting_finished", "data": {"success": True, "message": "Agent has finished processing the event and post creation."}}