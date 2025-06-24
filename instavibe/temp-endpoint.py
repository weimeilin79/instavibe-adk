from vertexai import agent_engines



agent_list = agent_engines.list()
print("Available Agent Engines:")
if agent_list:
    for agent in agent_list:
        # Assuming agent objects have 'display_name' and 'resource_name' attributes
        with open("temp_endpoint.txt", "w") as f:
            f.write(getattr(agent, 'resource_name', 'N/A'))
            print(f"  Display Name: {getattr(agent, 'display_name', 'N/A')}, Resource Name: {getattr(agent, 'resource_name', 'N/A')}")
else:
    print("  No agent engines found.")


print("-" * 20) # Added a separator for clarity

