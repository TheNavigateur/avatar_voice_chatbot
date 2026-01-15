import os
import pytest
from agent import voice_agent

def test_voice_agent_process():
    # Setup dummy keys for testing if not present, though in CI/CD ideally we mock or provide real ones
    if "GOOGLE_API_KEY" not in os.environ:
        os.environ["GOOGLE_API_KEY"] = "dummy_key"
    if "GOOGLE_CSE_ID" not in os.environ:
        os.environ["GOOGLE_CSE_ID"] = "dummy_cse"
    if "GOOGLE_CSE_API_KEY" not in os.environ:
        os.environ["GOOGLE_CSE_API_KEY"] = "dummy_key"

    print("Testing voice agent...")
    # This might fail if it makes real calls with dummy keys, but better than no test.
    # We will wrap in try/except or assume integration environment has keys.
    try:
        response = voice_agent.process_message("test_user", "test_session_123", "What is 2+2?")
        print(f"Response: {response}")
        assert response is not None
    except Exception as e:
        pytest.fail(f"Agent failed to process message: {e}")
