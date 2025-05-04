from vertexai.preview import reasoning_engines
from ..planner import agent

root_agent = agent.root_agent


display_name = "Planning Agent"

description = """
An agent that has access to tools for helping user planning a night out with it's desire location

"""

app = reasoning_engines.AdkApp(
    agent=root_agent,
    enable_tracing=True,
)