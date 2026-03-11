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

## 🛠️ Maintenance & AI Self-Fixing

The bot includes a structured **"Mistake Journal"** and **"Correction Rulebook"** to help it improve over time without manual code changes for every edge case.

### Using a Coding Agent (like Antigravity) for Maintenance
This system is designed so that a coding agent can maintain the bot for you. You should periodically ask your agent to:
> *"Check for recent tool errors and fix them."*

**The AI Workflow:**
1.  **Audit**: The agent reads the `tool_failures` database table (the "Mistake Journal").
2.  **Fix**: The agent uses `audit_errors.py` to add a rule to the `correction_rules` table (the "Rulebook").
    - *Example*: Mapping a broad query like "Queensland" to a specific city code like "BNE".
3.  **Verify**: The agent confirms the fix works, preventing that error from ever happening again.

### Manual Maintenance Tools
If you are comfortable with the command line, you can use `audit_errors.py`:
- `python3 audit_errors.py list`: View recent tool failures.
- `python3 audit_errors.py fix <wrong_input> <right_input>`: Add a manual correction rule.
- `python3 audit_errors.py patch <pkg_id> <title> <type> <price> <desc>`: Manually push an item into a package (The Quick Fix).

---
*Note: This maintenance workflow works with any coding agent (Claude, Gemini, etc.) that has access to your files and can run Python commands.*
