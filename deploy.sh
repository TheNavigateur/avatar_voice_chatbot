#!/bin/bash

# Configuration
SERVICE_NAME="avatar-voice-bot"
REGION="us-central1"

echo "Deploying $SERVICE_NAME to Google Cloud Run..."

# 1. Load Secrets
if [ -f secrets.sh ]; then
    source secrets.sh
else
    echo "Error: secrets.sh not found. Cannot deploy without API keys."
    exit 1
fi

# 2. Verify Essential Keys
REQUIRED_KEYS=("GOOGLE_API_KEY" "OPENAI_API_KEY" "ELEVENLABS_API_KEY")
MISSING_KEY=false

for key in "${REQUIRED_KEYS[@]}"; do
    if [ -z "${!key}" ]; then
        echo "Error: $key is not set in secrets.sh"
        MISSING_KEY=true
    fi
done

if [ "$MISSING_KEY" = true ]; then
    echo "Aborting deployment due to missing keys."
    exit 1
fi

# 3. Deploy using gcloud
# We manually inject the environment variables from our local shell into the Cloud Run instance
gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --region "$REGION" \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_API_KEY=$GOOGLE_API_KEY" \
  --set-env-vars "GOOGLE_CSE_ID=$GOOGLE_CSE_ID" \
  --set-env-vars "GOOGLE_CSE_API_KEY=$GOOGLE_CSE_API_KEY" \
  --set-env-vars "OPENAI_API_KEY=$OPENAI_API_KEY" \
  --set-env-vars "ELEVENLABS_API_KEY=$ELEVENLABS_API_KEY"

echo "Deployment command finished."
