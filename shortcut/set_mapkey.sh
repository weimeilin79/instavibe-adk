#!/bin/bash

# v7 - Corrected the jq parsing to look inside the .response object.
# This fixes the bug where the operation name was captured instead of the key name.

# --- Configuration ---
DISPLAY_NAME="Maps Platform API Key"
API_TO_RESTRICT="maps-javascript.googleapis.com"
# --- End of Configuration ---

# Ensure jq is installed
if ! command -v jq &> /dev/null; then
    echo "❌ ERROR: The 'jq' utility is required but not installed."
    echo "   Please install it (e.g., 'sudo apt-get install jq')."
    exit 1
fi

echo "✅ Starting the API key creation process..."

# 1. Check for an existing key to prevent duplicates.
echo "   - Checking for an existing key named '$DISPLAY_NAME'..."
EXISTING_KEY_NAME=$(gcloud services api-keys list \
  --filter="displayName='$DISPLAY_NAME'" \
  --format="value(name)")

if [ ! -z "$EXISTING_KEY_NAME" ]; then
  echo "❌ ERROR: A key with the name '$DISPLAY_NAME' already exists."
  echo "   To prevent creating a duplicate, please delete the old key from the Cloud Console and run again."
  exit 1
fi

echo "   - No existing key found. Creating a new API key..."

# 2. Create the key and capture its details from the JSON output.
# The --format=json command returns an Operation object. The key data is in the 'response' field.
API_OPERATION_JSON=$(gcloud services api-keys create \
  --display-name="$DISPLAY_NAME" \
  --format=json)

# CORRECTED PARSING LOGIC HERE
KEY_NAME=$(echo "$API_OPERATION_JSON" | jq -r '.response.name')
API_KEY_STRING=$(echo "$API_OPERATION_JSON" | jq -r '.response.keyString')

# --- DEBUG LINE ---
echo "   - DEBUG: Captured Key Name is: $KEY_NAME"
# --------------------

if [ -z "$KEY_NAME" ] || [ "$KEY_NAME" == "null" ] || [ -z "$API_KEY_STRING" ] || [ "$API_KEY_STRING" == "null" ]; then
    echo "❌ ERROR: Failed to parse the key details from the create command's output."
    echo "   Please check the gcloud command output above for issues."
    exit 1
fi

echo "   - Successfully created key. Now applying API restrictions..."
gcloud services api-keys update "$KEY_NAME" \
--clear-restrictions

# 3. Restrict the key using its correct name.
gcloud services api-keys update "$KEY_NAME" \
  --api-target="service=${API_TO_RESTRICT}" > /dev/null

if [ $? -ne 0 ]; then
    echo "❌ ERROR: Failed to restrict the API key."
    echo "   Please ensure you have run 'gcloud components update' and have the correct permissions (e.g., 'API Keys Admin')."
    exit 1
fi

echo "   - Successfully restricted key to use only the Maps JavaScript API."

echo ""
echo "🎉 --- SCRIPT COMPLETE --- 🎉"
echo "Your new API key has been created and restricted."
echo ""
echo "Your Maps Platform API Key is:"
echo "--------------------------------------------------"
echo "$API_KEY_STRING"
echo "--------------------------------------------------"