import logging
import os
import google.generativeai as genai
from typing import Optional

logger = logging.getLogger(__name__)

class MemoryAgent:
    def __init__(self):
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            logger.error("GOOGLE_API_KEY not found for MemoryAgent")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-2.0-flash")


    def update_structured_profile(self, current_profile: str, last_bot_message: str, user_message: str) -> str:
        """
        Rewrites the user profile based on new information.
        """
        prompt = f"""You are a Memory Manager for an AI Assistant. 
Your goal is to maintain a structured, first-person "About Me" document for the user.

**Current Profile:**
{current_profile}

**Conversation Context:**
Assistant asked: "{last_bot_message}"
User replied: "{user_message}"

**Instructions:**
1.  Update the **Current Profile** with any new information from the **User's reply**.
2.  Use the "Assistant asked" context to understand what the user is referring to (e.g., if Assistant asked about a party location, put the location under a "Party" heading).
3.  **Structure:** Use Markdown headers (##) for topics (e.g., ## Son's Birthday Party, ## Food Preferences).
4.  **Perspective:** ALWAYS write in the **First Person** (I, me, my).
5.  **Cleanliness:** Merge duplicate info. Keep it concise but detailed enough to be useful.
6.  **Output:** Return ONLY the updated Markdown profile. Do not include any other text.

**Example Update:**
*Context:* Bot: "Where is the party?" -> User: "Barnes"
*Result:*
## Son's Birthday Party
- Location: Barnes, London
"""
        try:
            response = self.model.generate_content(prompt)
            if response.text:
                logger.info("Memory Agent updated profile successfully.")
                return response.text
            else:
                logger.warning("Memory Agent returned empty text. Keeping old profile.")
                return current_profile
        except Exception as e:
            logger.error(f"Memory Agent failed: {e}")
            return current_profile
