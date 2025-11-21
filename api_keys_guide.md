# How to Get Your API Keys

To run the Voice Chatbot, you need keys for **Gemini** (the AI) and **Google Search** (the knowledge).

## 1. GOOGLE_API_KEY (Gemini)
1.  Go to [Google AI Studio](https://aistudio.google.com/).
2.  Click **Get API key**.
3.  Click **Create API key**.
4.  Copy the key string.

## 2. Google Search Keys
You need a **Search Engine ID** and an **API Key** for it.

### A. Create the Search Engine (GOOGLE_CSE_ID)
1.  Go to [Programmable Search Engine](https://programmablesearchengine.google.com/controlpanel/all).
2.  Click **Add**.
3.  **Name**: "Voice Bot Search".
4.  **What to search**: Select "Search the entire web".
5.  Click **Create**.
6.  Look for **"Search engine ID"** (format: `cx=...`).
7.  Copy this ID. This is your `GOOGLE_CSE_ID`.

### B. Enable the API and Get Key (GOOGLE_CSE_API_KEY)
1.  Go to the [Google Cloud Console - Custom Search API](https://console.cloud.google.com/apis/library/customsearch.googleapis.com).
2.  Select a project (create one if needed).
3.  Click **Enable**.
4.  Go to [Credentials](https://console.cloud.google.com/apis/credentials).
5.  Click **Create Credentials** > **API key**.
6.  Copy this key. This is your `GOOGLE_CSE_API_KEY`.

## 3. Set them in your terminal
Run these commands in your terminal (replace the values with your actual keys):

```bash
export GOOGLE_API_KEY="AIzaSy..."
export GOOGLE_CSE_ID="012345..."
export GOOGLE_CSE_API_KEY="AIzaSy..."
```

Then run the bot:
```bash
sh run.sh
```
