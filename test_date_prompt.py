from agent import VoiceAgent
import os

def test_date_prompt():
    # Source the environment variables from secrets.sh
    import subprocess
    command = ['bash', '-c', 'source secrets.sh && env']
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, text=True)
    for line in proc.stdout:
        (key, _, value) = line.partition('=')
        os.environ[key] = value.strip()
    
    agent = VoiceAgent()
    user_id = "test_user_prompt"
    session_id = "test_session_prompt"
    
    print("\n--- Phase 1: Adventurous Trip to Maldives ---")
    res1 = agent.process_message(user_id, session_id, "I want to plan an adventurous trip to the Maldives")
    print(f"Bot Output: {res1}\n")

if __name__ == "__main__":
    test_date_prompt()
