Some Updates TODO

```
# instavibe-bootstrap

cd  ~/instavibe-bootstrap/agents
. ~/instavibe-bootstrap/set_env.sh
source ~/instavibe-bootstrap/env/bin/activate



export PLANNER_AGENT_URL=http://localhost:10003
export PLATFORM_MPC_CLIENT_URL=http://localhost:10002
export SOCIAL_AGENT_URL=http://localhost:10001

export REMOTE_AGENT_ADDRESSES=${PLANNER_AGENT_URL},${PLATFORM_MPC_CLIENT_URL},${SOCIAL_AGENT_URL}

adk web

python -m planner.a2a_server
python -m platform_mcp_client.a2a_server
python -m social.a2a_server


cd ~/instavibe-bootstrap/agents/
. ~/instavibe-bootstrap/set_env.sh
source ~/instavibe-bootstrap/env/bin/activate
export PLANNER_AGENT_URL=$(gcloud run services list --platform=managed --region=us-central1 --format='value(URL)' | grep planner-agent)
export PLATFORM_MPC_CLIENT_URL=$(gcloud run services list --platform=managed --region=us-central1 --format='value(URL)' | grep platform-mcp-client)
export SOCIAL_AGENT_URL=$(gcloud run services list --platform=managed --region=us-central1 --format='value(URL)' | grep social-agent)

export REMOTE_AGENT_ADDRESSES=${PLANNER_AGENT_URL},${PLATFORM_MPC_CLIENT_URL},${SOCIAL_AGENT_URL}


adk deploy agent_engine \
--project $GOOGLE_CLOUD_PROJECT \
--region $GOOGLE_CLOUD_LOCATION \
--staging_bucket gs://$GOOGLE_CLOUD_PROJECT-agent-engine \
--trace_to_cloud \
--requirements_file orchestrate/requirements.txt \
orchestrate


gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:service-$PROJECT_NUMBER@gcp-sa-aiplatform-re.iam.gserviceaccount.com" \
    --role="roles/viewer"


. ~/instavibe-bootstrap/set_env.sh

# 2. Navigate to the directory containing your orchestrating cloudbuild.yaml
cd ~/instavibe-bootstrap/agents

```
