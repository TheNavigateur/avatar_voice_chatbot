# Ray and Rae: AI Package Assistant

**Ray and Rae** is an intelligent AI assistant designed to create and book packages for holidays, parties, shopping, and local activities.

Built on the **Google Agent Development Kit (ADK)** and **Gemini 2.0 Flash**, it features:
*   **Natural Voice Interface**: Talk to Ray and Rae to plan your trip or event.
*   **Dynamic Packaging**: The agent intelligently groups items (flights, hotels, tickets) into "Packages".
*   **One-Click Booking**: Simulate booking entire packages with automatic rollback handling for failures.
*   **3D Avatars**: Interact with 3D avatars (GLB/VRM) for a more immersive experience.

## Prerequisites

1.  **Python 3.10+**
2.  **API Keys**:
    *   **GOOGLE_API_KEY**: Gemini Model access.
    *   **GOOGLE_CSE_ID** & **GOOGLE_CSE_API_KEY**: For real-time search capabilities.
    *   **(Optional) OPENAI_API_KEY**: For OpenAI TTS voices.
    *   **(Optional) ELEVENLABS_API_KEY**: For ElevenLabs TTS voices.

## Setup

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Configure Environment**:
    Create a `secrets.sh` file (ignored by git) or set variables directly:
    ```bash
    export GOOGLE_API_KEY="your_key"
    export GOOGLE_CSE_ID="your_cse_id"
    export GOOGLE_CSE_API_KEY="your_cse_key"
    export OPENAI_API_KEY="your_openai_key" # Optional
    ```

## Running

Start the server:
```bash
source secrets.sh && python3 app.py
```

1.  Open **`http://localhost:8001`**.
2.  **Speak** to Ray and Rae: *"I want to plan a dinosaur-themed birthday party."*
3.  **Watch** as packages appear in the right-hand panel.
4.  **Click "Book Package"** to complete the simulated transaction.

## Features

*   **Session Management**: Remembers context during your conversation.
*   **Package API**:
    *   `GET /api/session/{id}/packages`: Retrieve current packages.
    *   `POST /api/packages/{id}/book`: Execute booking transaction.
*   **Mock Booking Service**: Simulates API calls with success/failure probability for testing rollback logic.
