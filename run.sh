#!/bin/bash
echo "Starting Google ADK Voice Chatbot..."
# Load secrets if available
if [ -f secrets.sh ]; then
    source secrets.sh
else
    echo "Warning: secrets.sh not found. Ensure API keys are set."
fi
python3 app.py
