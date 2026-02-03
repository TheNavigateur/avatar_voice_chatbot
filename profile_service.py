from database import get_db_connection
import logging

logger = logging.getLogger(__name__)

class ProfileService:
    
    @staticmethod
    def get_profile(user_id: str) -> str:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT content FROM user_profiles WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return row['content']
        
        # Default content if new user
        return "# About Me\n- I am a new user."

    @staticmethod
    def update_profile(user_id: str, content: str):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_profiles (user_id, content) 
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET content=excluded.content
        """, (user_id, content))
        conn.commit()
        conn.close()
        logger.info(f"Updated profile for user: {user_id}")
        
    @staticmethod
    def append_to_profile(user_id: str, fact: str):
        current_content = ProfileService.get_profile(user_id)
        new_content = current_content + f"\n- {fact}"
        ProfileService.update_profile(user_id, new_content)
        return new_content
