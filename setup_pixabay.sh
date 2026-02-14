#!/bin/bash

# Add your Pixabay API key here
# Get it from: https://pixabay.com/api/docs/ (after signing up/logging in)

echo "Adding Pixabay API key to secrets.sh..."

# Prompt for API key
read -p "Enter your Pixabay API key: " PIXABAY_KEY

# Add to secrets.sh
echo "" >> secrets.sh
echo "# Pixabay API for image search" >> secrets.sh
echo "export PIXABAY_API_KEY=\"$PIXABAY_KEY\"" >> secrets.sh

echo "✅ Added PIXABAY_API_KEY to secrets.sh"
echo ""
echo "Now restart the server:"
echo "  pkill -f uvicorn && bash run.sh"
