# Image Search API Setup Guide

## Option 1: Pixabay (Recommended - Free & Most Generous)

1. Go to https://pixabay.com/api/docs/
2. Sign up for free
3. Get your API key
4. Add to `secrets.sh`:
   ```bash
   export PIXABAY_API_KEY="your_api_key_here"
   ```

**Limits:** 5,000 requests/hour (free) - **25x more than Pexels!**
**Attribution:** Optional (not required)

## Option 2: Pexels (Alternative - Free)

1. Go to https://www.pexels.com/api/
2. Click "Get Started"
3. Create a free account
4. Get your API key
5. Add to `secrets.sh`:
   ```bash
   export PEXELS_API_KEY="your_api_key_here"
   ```

**Limits:** 200 requests/hour (free)

## Option 3: Google Custom Search (Most Accurate)

1. Go to https://console.cloud.google.com/
2. Enable Custom Search API
3. Create a Custom Search Engine at https://cse.google.com/cse/
4. Get your API key and Search Engine ID
5. Add to `secrets.sh`:
   ```bash
   export GOOGLE_SEARCH_ENGINE_ID="your_cx_id_here"
   # GOOGLE_API_KEY should already be set
   ```

**Limits:** 100 queries/day (free)

## Quick Start (Pexels)

```bash
# Add to secrets.sh
echo 'export PEXELS_API_KEY="your_key_here"' >> secrets.sh

# Restart the server
source secrets.sh
bash run.sh
```

The system will automatically try Pexels → Pixabay → Google in that order.
