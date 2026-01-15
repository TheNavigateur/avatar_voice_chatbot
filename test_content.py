import pytest

def test_content_creation():
    try:
        from google.genai.types import Content, Part
        c = Content(role="user", parts=[Part(text="Hello")])
        print(f"Created content: {c}")
        print(f"Role: {c.role}")
        assert c.role == "user"
    except ImportError as e:
        pytest.fail(f"Import failed: {e}")
    except Exception as e:
        pytest.fail(f"Error: {e}")
