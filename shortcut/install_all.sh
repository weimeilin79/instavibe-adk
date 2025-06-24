#!/bin/bash

# ==============================================================================
#
# InstaVibe Bootstrap - Consolidated Setup Script for InstaVibe app and DB
#
# ==============================================================================

# --- Script Configuration ---
# Stop script on any error
set -e
# Treat unset variables as an error
set -u
# Pipefail
set -o pipefail


# This function will be called when the script exits on an error.
error_handler() {
  local exit_code=$?
  echo ""
  echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
  echo "❌ SCRIPT FAILED with exit code $exit_code at line: $BASH_LINENO"
  echo "The command that failed was: '$BASH_COMMAND'"
  echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
  echo ""
  echo "The terminal will now pause. Press [Ctrl+C] to terminate."
  read
}
# We 'trap' the ERR signal and call our error_handler function.
trap 'error_handler' ERR
# ------------------------------------

# --- User-configurable variables ---
REPO_URL="https://github.com/GoogleCloudPlatform/instavibe-adk.git"
REPO_DIR_NAME="instavibe-adk"
SPANNER_INSTANCE_ID="instavibe-graph-instance"
SPANNER_DATABASE_ID="graphdb"
ARTIFACT_REPO_NAME="introveally-repo"
GOOGLE_CLOUD_LOCATION="us-central1"
MAPS_API_KEY_DISPLAY_NAME="Maps Platform API Key - InstaVibe"
IMAGE_NAME="instavibe-webapp"
SERVICE_NAME="instavibe"

# --- Helper Functions ---
log() {
  echo "✅  $1"
}

check_command() {
  if ! command -v "$1" &>/dev/null; then
    echo "❌ Error: Command not found: '$1'. Please install it and make sure it's in your PATH."
    exit 1 # This will trigger the error trap
  fi
}

# --- Pre-flight Checks ---
log "Running pre-flight checks..."
check_command "gcloud"
check_command "git"
check_command "python"
check_command "pip"
check_command "jq"
log "All required tools are installed."

log "Checking gcloud authentication status..."
if ! gcloud auth print-access-token -q &>/dev/null; then
  echo "❌ Error: You are not authenticated with gcloud. Please run 'gcloud auth login' and 'gcloud auth application-default login'."
  exit 1
fi
log "gcloud is authenticated."


# --- Step 1: Set Google Cloud Project ID ---
log "--- Step 1: Setting Google Cloud Project ID ---"
PROJECT_FILE="$HOME/project_id.txt"

if [ -f "$PROJECT_FILE" ]; then
    PROJECT_ID=$(cat "$PROJECT_FILE")
    log "Found existing project ID in $PROJECT_FILE: $PROJECT_ID"
    read -p "Do you want to use this project ID? (y/n): " use_existing
    if [[ "$use_existing" != "y" ]]; then
        read -p "Please enter your new Google Cloud project ID: " PROJECT_ID
    fi
else
    read -p "Please enter your Google Cloud project ID: " PROJECT_ID
fi

if [[ -z "$PROJECT_ID" ]]; then
  echo "❌ Error: No project ID was entered."
  exit 1
fi

echo "$PROJECT_ID" > "$PROJECT_FILE"
log "Successfully saved project ID '$PROJECT_ID' to $PROJECT_FILE"
gcloud config set project "$PROJECT_ID" --quiet
log "Set gcloud active project to '$PROJECT_ID'."

# ==============================================================================
# === FIX: Export the PROJECT_ID so child processes like python can see it. ===
export PROJECT_ID
export GOOGLE_CLOUD_PROJECT="$PROJECT_ID"
log "Exported PROJECT_ID and GOOGLE_CLOUD_PROJECT for child processes."
# ==============================================================================


# --- Step 2: Discover Environment Variables & Clone Repo ---
log "--- Step 2: Discovering environment variables and cloning repo ---"
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")
SERVICE_ACCOUNT_NAME=$(gcloud compute project-info describe --format="value(defaultServiceAccount)")
log "Project ID and Service Account discovered."

REPO_DIR_PATH="$HOME/$REPO_DIR_NAME"
if [ -d "$REPO_DIR_PATH" ]; then
    log "Repository directory '$REPO_DIR_PATH' already exists. Skipping clone."
else
    log "Cloning repository..."
    git clone "$REPO_URL" "$REPO_DIR_PATH"
    log "Repository cloned successfully."
fi

log "Creating environment file at '$REPO_DIR_PATH/set_env.sh'..."
cat > "$REPO_DIR_PATH/set_env.sh" << EOL
#!/bin/bash
export PROJECT_ID="${PROJECT_ID}"
export GOOGLE_CLOUD_PROJECT="${PROJECT_ID}"
export PROJECT_NUMBER="${PROJECT_NUMBER}"
export REGION="${GOOGLE_CLOUD_LOCATION}"
export GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION}"
export REPO_NAME="${ARTIFACT_REPO_NAME}"
export SPANNER_INSTANCE_ID="${SPANNER_INSTANCE_ID}"
export SPANNER_DATABASE_ID="${SPANNER_DATABASE_ID}"
EOL
log "Environment file created."


# --- Step 3: Enable Google Cloud APIs ---
log "--- Step 3: Enabling required Google Cloud APIs (this may take a few minutes) ---"
gcloud services enable  run.googleapis.com \
                        cloudfunctions.googleapis.com \
                        cloudbuild.googleapis.com \
                        artifactregistry.googleapis.com \
                        spanner.googleapis.com \
                        apikeys.googleapis.com \
                        iam.googleapis.com \
                        compute.googleapis.com \
                        aiplatform.googleapis.com \
                        cloudresourcemanager.googleapis.com \
                        maps-backend.googleapis.com
log "All necessary APIs enabled."


# --- Step 4: Grant IAM Permissions ---
log "--- Step 4: Granting IAM Roles to Service Account: $SERVICE_ACCOUNT_NAME ---"
declare -a ROLES=(
  "roles/spanner.admin" "roles/spanner.databaseUser" "roles/artifactregistry.admin"
  "roles/run.admin" "roles/iam.serviceAccountUser" "roles/serviceusage.serviceUsageAdmin"
  "roles/aiplatform.user" "roles/logging.logWriter" "roles/logging.viewer"
)

for ROLE in "${ROLES[@]}"; do
  log "Assigning role: $ROLE"
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SERVICE_ACCOUNT_NAME" \
    --role="$ROLE" \
    --condition=None > /dev/null
done
log "All project-level IAM roles have been assigned."


# --- Step 5: Create Artifact Registry Repository ---
log "--- Step 5: Creating Artifact Registry Repository: $ARTIFACT_REPO_NAME ---"
if gcloud artifacts repositories describe "$ARTIFACT_REPO_NAME" --location="$GOOGLE_CLOUD_LOCATION" &>/dev/null; then
  log "Artifact Registry repository '$ARTIFACT_REPO_NAME' already exists. Skipping."
else
  gcloud artifacts repositories create "$ARTIFACT_REPO_NAME" \
    --repository-format=docker \
    --location="$GOOGLE_CLOUD_LOCATION" \
    --description="Docker repository for InstaVibe workshop"
  log "Successfully created Artifact Registry repository."
fi


# --- Step 6: Create Spanner Instance and Database ---
log "--- Step 6: Creating Spanner Instance & Database ---"
if gcloud spanner instances describe "$SPANNER_INSTANCE_ID" &>/dev/null; then
  log "Spanner instance '$SPANNER_INSTANCE_ID' already exists. Skipping."
else
  gcloud spanner instances create "$SPANNER_INSTANCE_ID" \
    --config=regional-us-central1 \
    --description="GraphDB Instance InstaVibe" \
    --processing-units=100 \
    --edition=ENTERPRISE
  log "Successfully created Spanner instance."
fi

if gcloud spanner databases describe "$SPANNER_DATABASE_ID" --instance="$SPANNER_INSTANCE_ID" &>/dev/null; then
  log "Spanner database '$SPANNER_DATABASE_ID' already exists. Skipping."
else
  gcloud spanner databases create "$SPANNER_DATABASE_ID" \
    --instance="$SPANNER_INSTANCE_ID" \
    --database-dialect=GOOGLE_STANDARD_SQL
  log "Successfully created Spanner database."
fi


# --- Step 7: Grant Database-Level IAM Role ---
log "--- Step 7: Granting Spanner database access to the service account ---"
gcloud spanner databases add-iam-policy-binding "$SPANNER_DATABASE_ID" \
  --instance="$SPANNER_INSTANCE_ID" \
  --member="serviceAccount:$SERVICE_ACCOUNT_NAME" \
  --role="roles/spanner.databaseUser" \
  --project="$PROJECT_ID"
log "Successfully granted database-level access."


# --- Step 8: Create and Restrict Google Maps API Key ---
log "--- Step 8: Creating and Restricting Google Maps API Key ---"
EXISTING_KEY_NAME=$(gcloud services api-keys list --filter="displayName='$MAPS_API_KEY_DISPLAY_NAME'" --format="value(name)")

if [ ! -z "$EXISTING_KEY_NAME" ]; then
    log "An API key named '$MAPS_API_KEY_DISPLAY_NAME' already exists. Deleting it to create a new one."
    gcloud services api-keys delete "$EXISTING_KEY_NAME" --quiet
    log "Old key deleted."
fi

log "Creating a new API key named '$MAPS_API_KEY_DISPLAY_NAME'..."
API_OPERATION_JSON=$(gcloud services api-keys create \
  --display-name="$MAPS_API_KEY_DISPLAY_NAME" \
  --format=json)

KEY_NAME=$(echo "$API_OPERATION_JSON" | jq -r '.response.name')
GOOGLE_MAPS_API_KEY=$(echo "$API_OPERATION_JSON" | jq -r '.response.keyString')

if [ -z "$KEY_NAME" ] || [ "$KEY_NAME" == "null" ] || [ -z "$GOOGLE_MAPS_API_KEY" ] || [ "$GOOGLE_MAPS_API_KEY" == "null" ]; then
    echo "❌ ERROR: Failed to parse key details from gcloud output."
    exit 1
fi
log "Successfully created key. Now applying restrictions..."
gcloud services api-keys update "$KEY_NAME" --clear-restrictions
gcloud services api-keys update "$KEY_NAME" --api-target="service=maps-javascript.googleapis.com" > /dev/null
log "API Key has been created and restricted to the Maps JavaScript API."


# --- Step 9: Setup Python Environment & Application Data ---
log "--- Step 9: Setting up Python environment and populating database ---"
VENV_PATH="$REPO_DIR_PATH/env"
if [ -d "$VENV_PATH" ]; then
    log "Python virtual environment 'env' already exists. Re-activating it."
else
    python -m venv "$VENV_PATH"
    log "Created Python virtual environment."
fi

log "Activating virtual environment and installing dependencies..."
source "$VENV_PATH/bin/activate"
pip install --upgrade pip
pip install -r "$REPO_DIR_PATH/requirements.txt"
log "Python dependencies installed."

log "Running application setup script to populate database..."
cd "$REPO_DIR_PATH/instavibe"
python setup.py
cd "$REPO_DIR_PATH"
log "Application database populated."


# --- Step 10: Build and Deploy the MCP Tool Server (Stage 1) ---
log "--- Step 10: Build and Deploy the MCP Tool Server (Stage 1) ---"
. "$REPO_DIR_PATH/set_env.sh"
cd "$REPO_DIR_PATH/tools/instavibe"

export IMAGE_TAG="latest"
export MCP_IMAGE_NAME="mcp-tool-server"
export IMAGE_PATH="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${MCP_IMAGE_NAME}:${IMAGE_TAG}"
export MCP_SERVICE_NAME="mcp-tool-server"

log "Building MCP Tool Server container..."
gcloud builds submit . \
  --tag=${IMAGE_PATH} \
  --project=${PROJECT_ID}

log "Deploying MCP Tool Server to Cloud Run (without InstaVibe URL)..."
gcloud run deploy ${MCP_SERVICE_NAME} \
  --image=${IMAGE_PATH} \
  --platform=managed \
  --region=${REGION} \
  --allow-unauthenticated \
  --set-env-vars="APP_HOST=0.0.0.0" \
  --set-env-vars="APP_PORT=8080" \
  --set-env-vars="GOOGLE_GENAI_USE_VERTEXAI=TRUE" \
  --set-env-vars="GOOGLE_CLOUD_LOCATION=${REGION}" \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID}" \
  --project=${PROJECT_ID} \
  --min-instances=1
log "MCP Tool Server deployed (Stage 1). It will be updated with the InstaVibe URL later."
MCP_TOOL_SERVER_URL=$(gcloud run services describe ${MCP_SERVICE_NAME} --platform=managed --region=${REGION} --format='value(status.url)')


# --- Step 11: Build and Deploy the Planner Agent ---
log "--- Step 11: Build and Deploy the Planner Agent ---"
. "$REPO_DIR_PATH/set_env.sh"
cd "$REPO_DIR_PATH/agents"

export IMAGE_TAG="latest"
export AGENT_NAME="planner"
export IMAGE_NAME="planner-agent"
export IMAGE_PATH="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${IMAGE_NAME}:${IMAGE_TAG}"
export PLANNER_SERVICE_NAME="planner-agent"
export PUBLIC_URL="https://planner-agent-${PROJECT_NUMBER}.${REGION}.run.app"

log "Building ${AGENT_NAME} agent..."
gcloud builds submit . \
  --config=cloudbuild-build.yaml \
  --project=${PROJECT_ID} \
  --region=${REGION} \
  --substitutions=_AGENT_NAME=${AGENT_NAME},_IMAGE_PATH=${IMAGE_PATH}
log "Image built and pushed to: ${IMAGE_PATH}"

log "Deploying ${AGENT_NAME} agent to Cloud Run..."
gcloud run deploy ${PLANNER_SERVICE_NAME} \
  --image=${IMAGE_PATH} \
  --platform=managed \
  --region=${REGION} \
  --set-env-vars="A2A_HOST=0.0.0.0" \
  --set-env-vars="A2A_PORT=8080" \
  --set-env-vars="GOOGLE_GENAI_USE_VERTEXAI=TRUE" \
  --set-env-vars="GOOGLE_CLOUD_LOCATION=${REGION}" \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID}" \
  --set-env-vars="PUBLIC_URL=${PUBLIC_URL}" \
  --allow-unauthenticated \
  --project=${PROJECT_ID} \
  --min-instances=1
log "${AGENT_NAME} agent deployed successfully."


# --- Step 12: Build Remaining Agents with Cloud Build ---
log "--- Step 12: Build Remaining Agents (platform-mcp-client, social-agent) ---"
. "$REPO_DIR_PATH/set_env.sh"
cd "$REPO_DIR_PATH/agents"
export MCP_SERVER_URL="${MCP_TOOL_SERVER_URL}/sse"

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
log "Remaining agents built and deployed via Cloud Build."


# --- Step 13: Deploy Orchestrator Agent with ADK ---
log "--- Step 13: Deploying Orchestrator Agent with ADK ---"
cd "$REPO_DIR_PATH/agents/"
. "$REPO_DIR_PATH/set_env.sh"
source "$VENV_PATH/bin/activate"

log "Fetching agent service URLs..."
PLATFORM_MPC_CLIENT_URL=$(gcloud run services list --platform=managed --region=${REGION} --format='value(URL)' | grep platform-mcp-client)
PLANNER_AGENT_URL=$(gcloud run services list --platform=managed --region=${REGION} --format='value(URL)' | grep planner-agent)
SOCIAL_AGENT_URL=$(gcloud run services list --platform=managed --region=${REGION} --format='value(URL)' | grep social-agent)

export REMOTE_AGENT_ADDRESSES="${PLANNER_AGENT_URL},${PLATFORM_MPC_CLIENT_URL},${SOCIAL_AGENT_URL}"
log "Updating .env file for orchestrator..."
sed -i.bak "s|^\(O\?REMOTE_AGENT_ADDRESSES\)=.*|REMOTE_AGENT_ADDRESSES=${REMOTE_AGENT_ADDRESSES}|" "$REPO_DIR_PATH/agents/orchestrate/.env"

log "Deploying orchestrator agent via ADK..."
# The ADK is expected to be installed as part of requirements.txt
adk deploy agent_engine \
--display_name "orchestrate-agent" \
--project $GOOGLE_CLOUD_PROJECT \
--region $GOOGLE_CLOUD_LOCATION \
--staging_bucket gs://$GOOGLE_CLOUD_PROJECT-agent-engine \
--trace_to_cloud \
--requirements_file orchestrate/requirements.txt \
orchestrate
log "Orchestrator agent deployment initiated. This may take a few minutes to complete."


# --- Step 14: Get Orchestrator Agent Endpoint ID ---
log "--- Step 14: Getting Orchestrator Agent Endpoint ID ---"
. "$REPO_DIR_PATH/set_env.sh"
cd "$REPO_DIR_PATH/instavibe/"
source "$VENV_PATH/bin/activate"

log "Running script to retrieve the orchestrator agent endpoint ID..."
python temp-endpoint.py
export ORCHESTRATE_AGENT_ID=$(cat temp_endpoint.txt)
log "ORCHESTRATE_AGENT_ID set to: ${ORCHESTRATE_AGENT_ID}"


# --- Step 15: Grant IAM Role to AI Platform Service Agent ---
log "--- Step 15: Granting IAM Role to AI Platform Service Agent ---"
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:service-$PROJECT_NUMBER@gcp-sa-aiplatform-re.iam.gserviceaccount.com" \
    --role="roles/viewer" \
    --condition=None > /dev/null
log "Granted roles/viewer to AI Platform service agent."


# --- Step 16: Build InstaVibe Application Container ---
log "--- Step 16: Building the InstaVibe application container ---"
IMAGE_PATH="${GOOGLE_CLOUD_LOCATION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO_NAME}/${IMAGE_NAME}:latest"

cd "$REPO_DIR_PATH/instavibe"
gcloud builds submit . --tag="${IMAGE_PATH}" --project="${PROJECT_ID}"
cd "$REPO_DIR_PATH"
log "Container image successfully built and pushed to Artifact Registry."


# --- Step 17: Deploy InstaVibe Application to Cloud Run ---
log "--- Step 17: Deploying the InstaVibe application to Cloud Run ---"
gcloud run deploy "${SERVICE_NAME}" \
  --image="${IMAGE_PATH}" \
  --platform=managed \
  --region="${GOOGLE_CLOUD_LOCATION}" \
  --allow-unauthenticated \
  --set-env-vars="SPANNER_INSTANCE_ID=${SPANNER_INSTANCE_ID}" \
  --set-env-vars="SPANNER_DATABASE_ID=${SPANNER_DATABASE_ID}" \
  --set-env-vars="APP_HOST=0.0.0.0" \
  --set-env-vars="APP_PORT=8080" \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID}" \
  --set-env-vars="GOOGLE_MAPS_API_KEY=${GOOGLE_MAPS_API_KEY}" \
  --set-env-vars="ORCHESTRATE_AGENT_ID=${ORCHESTRATE_AGENT_ID}" \
  --project="${PROJECT_ID}" \
  --min-instances=1 \
  --cpu=2 \
  --memory=2Gi
log "Application successfully deployed to Cloud Run."
INSTAVIBE_SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --platform=managed --region=${GOOGLE_CLOUD_LOCATION} --format='value(status.url)')


# --- Step 18: Update MCP Tool Server with InstaVibe URL (Stage 2) ---
log "--- Step 18: Updating MCP Tool Server with InstaVibe URL (Stage 2) ---"
export INSTAVIBE_BASE_URL="${INSTAVIBE_SERVICE_URL}/api"
gcloud run services update ${MCP_SERVICE_NAME} \
    --platform=managed \
    --region=${REGION} \
    --update-env-vars="INSTAVIBE_BASE_URL=${INSTAVIBE_BASE_URL}" \
    --project=${PROJECT_ID}
log "MCP Tool Server successfully updated with the InstaVibe API endpoint."


# --- Unset the trap if we reach the end successfully ---
trap - ERR

# --- Final Success Message ---
echo ""
echo "==========================================================================="
echo "🚀 InstaVibe Bootstrap Setup is Complete! 🚀"
echo "==========================================================================="
echo ""
echo "All cloud resources have been provisioned and services are being deployed."
echo "Note: Some services like the orchestrator may take a few more minutes to become fully available."
echo ""
echo "✅ InstaVibe Web Application:"
echo "   ${INSTAVIBE_SERVICE_URL}"
echo ""
echo "✅ MCP Tool Server:"
echo "   ${MCP_TOOL_SERVER_URL}"
echo ""
echo "✅ Deployed Agents (URLs):"
echo "   - Planner Agent: ${PLANNER_AGENT_URL}"
echo "   - Platform MPC Client: ${PLATFORM_MPC_CLIENT_URL}"
echo "   - Social Agent: ${SOCIAL_AGENT_URL}"
echo ""
echo ""
echo "==========================================================================="
echo ""