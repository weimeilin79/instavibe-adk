from google.adk.agents import Agent
from google.adk.tools import google_search



root_agent = Agent(
    name="location_search_agent",
    model="gemini-2.0-flash",
    description="Agent to help user planning a night out with it's desire location.",
    instruction="Suggest some creative and fun dating plans for this upcoming weekend in the desire location. Include options for different budgets (free, $, $$, $$$) and interests (e.g., outdoors, arts, food, nightlife, unique events). Try to find specific, current events or places happening this weekend if possible. ",
    tools=[google_search]
)

