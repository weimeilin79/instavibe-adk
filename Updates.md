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

```
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:service-$PROJECT_NUMBER@gcp-sa-aiplatform-re.iam.gserviceaccount.com" \
    --role="roles/viewer"
```

. ~/instavibe-bootstrap/set_env.sh

# 2. Navigate to the directory containing your orchestrating cloudbuild.yaml
cd ~/instavibe-bootstrap/agents

# 3. Trigger the Cloud Build
# Cloud Build will pick up the substitution values from the environment
# variables that were exported by set_env.sh.
gcloud builds submit . \
  --config=cloudbuild.yaml \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --substitutions=\
_PROJECT_ID="${PROJECT_ID}",\
_PROJECT_NUMBER="${PROJECT_NUMBER}",\
_REGION="${REGION}",\
_REPO_NAME="${REPO_NAME}",\
_SPANNER_INSTANCE_ID="${SPANNER_INSTANCE_ID}",\
_SPANNER_DATABASE_ID="${SPANNER_DATABASE_ID}",\
_MCP_SERVER_URL="${MCP_SERVER_URL}"


gcloud builds submit . \
  --config=cloudbuild-social-only.yaml \
  --project="premium-bastion-461814-g8" \
  --region="us-central1" \
  --substitutions=\
_PROJECT_ID="premium-bastion-461814-g8",\
_PROJECT_NUMBER="577295170744",\
_REGION="us-central1",\
_REPO_NAME="introveally-repo",\
_SPANNER_INSTANCE_ID="instavibe-graph-instance",\
_SPANNER_DATABASE_ID="graphdb"
