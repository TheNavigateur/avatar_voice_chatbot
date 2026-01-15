from google.adk.sessions import InMemorySessionService
import inspect
import pytest

def test_session_service_signature_and_creation():
    # Check the actual signature
    svc = InMemorySessionService()
    print("get_session signature:", inspect.signature(svc.get_session))
    print("create_session signature:", inspect.signature(svc.create_session))

    # Try to create and get a session
    try:
        session = svc.create_session_sync(app_name="test_app", user_id="test_user", session_id="test_session")
        print(f"Created session: {session.id}")
        assert session.id == "test_session"
        
        # Try to get it back
        # Assuming get_session_sync exists based on naming convention, if not we will catch it in the next run
        # If get_session is sync (unlikely if create is async), checking signature would reveal it.
        # But for now let's try get_session_sync if available, or just skip if we can't confirm.
        # Actually, let's just assert on the created session as we know that works

    except Exception as e:
        import traceback
        traceback.print_exc()
        pytest.fail(f"Error in session test: {e}")
