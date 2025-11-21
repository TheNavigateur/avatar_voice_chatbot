# Google ADK Voice Chatbot

This project implements a voice chatbot using **Google's Agent Development Kit (ADK)**.
It uses the **Google Search Tool** to answer queries and provides a web-based voice interface.

## Prerequisites

1.  **Python 3.10+**
2.  **Google Cloud Project** with:
    *   **Gemini API** (Vertex AI or AI Studio)
    *   **Custom Search API**

## Setup

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Get API Keys**:
    *   **GOOGLE_API_KEY**: Get from [Google AI Studio](https://aistudio.google.com/).
    *   **GOOGLE_CSE_ID**: Create a search engine at [Programmable Search Engine](https://programmablesearchengine.google.com/).
    *   **GOOGLE_CSE_API_KEY**: Get from [Google Cloud Console](https://console.cloud.google.com/apis/credentials).

3.  **Set Environment Variables**:
    ```bash
    export GOOGLE_API_KEY="your_gemini_key"
    export GOOGLE_CSE_ID="your_cse_id"
    export GOOGLE_CSE_API_KEY="your_cse_key"
    ```

## Running

Run the application:
```bash
sh run.sh
```

Open your browser to `http://localhost:8000`.
Click the microphone button and ask a question!
