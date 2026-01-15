from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
import pytest

def test_session_sync_creation():
    svc = InMemorySessionService()
    session = svc.create_session_sync(app_name="test_app", user_id="test_user", session_id="test_session")
    print(f"Session type: {type(session)}")
    print(f"Session attributes: {[a for a in dir(session) if not a.startswith('_')]}")
    print(f"Session: {session}")
    assert session is not None
