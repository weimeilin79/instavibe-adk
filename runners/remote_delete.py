from vertexai import agent_engines

#print("Listing Agent Engines:")
#agent_list = agent_engines.list()



agent_list = agent_engines.list()
print("Available Agent Engines:")
if agent_list:
    for agent in agent_list:
        # Assuming agent objects have 'display_name' and 'resource_name' attributes
        print(f"  Display Name: {getattr(agent, 'display_name', 'N/A')}, Resource Name: {getattr(agent, 'resource_name', 'N/A')}")
else:
    print("  No agent engines found.")
print("-" * 20) # Added a separator for clarity


agent_engine = agent_engines.get('projects/789872749985/locations/us-central1/reasoningEngines/6601793268608925696')
agent_engines.delete('projects/789872749985/locations/us-central1/reasoningEngines/6601793268608925696')



