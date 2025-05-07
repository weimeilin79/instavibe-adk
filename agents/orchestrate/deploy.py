from orchestrate import agent
from vertexai import agent_engines
from vertexai.preview.reasoning_engines import AdkApp

root_agent = agent.root_agent


display_name = "Orchestrate Agent"

description = """
  This is the agent responsible for choosing which remote agents to send
  tasks to and coordinate their work on helping user to get social 
"""

app = AdkApp(
    agent=root_agent,
    enable_tracing=True,
)


remote_agent = agent_engines.create(
    agent,
    requirements="./requirements.txt",
)