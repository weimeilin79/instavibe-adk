```bash
cd datecoach/instavibe
 python app.py

cd datecoach/tools
python mcp_server.py


cd datecoach/agents
python -m planner.a2a_server 
python -m social.a2a_server
python -m introvertally.a2a_server


python -m orchestrate.run_orchestrator
```


```text
First, use the `send_task` tool with the 'Social Profile Agent' to get the social profiles (posts, events, friends) for Mike and Bob based on their Instavibe activity.

Next, using the profile information you gathered and knowledge about Boston for this weekend, create a detailed, tailored night-out plan for Mike and Bob. Make sure to consider their interests and potential budget options shown in their profiles. Show me the complete plan.

Finally, after generating the complete plan, use the `send_task` tool again to post it. Set the `agent_name` argument to 'Instavibe Posting Agent'. For the `message` argument, include the full text of the plan you just created, clearly state that the author is Alice, and suggest a positive sentiment for the post. For example, the message could be structured like: "Post the following plan to Instavibe: [Insert the full plan text here]. Make the sentiment positive. I'm Alice."
```

```
python -m app.agent_engine_app --set-env-vars "AGENT_BASE_URL=http://localhost:8080;REMOTE_AGENT_ADDRESSES=https://social-agent-service-789872749985.us-central1.run.app,https://planner-agent-service-789872749985.us-central1.run.app,https://platform-mcp-client-789872749985.us-central1.run.app"

```