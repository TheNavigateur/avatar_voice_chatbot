import os
import sys

def check_prompt_file(filepath, required_keywords):
    if not os.path.exists(filepath):
        print(f"ERROR: {filepath} not found!")
        sys.exit(1)
    
    with open(filepath, "r") as f:
        content = f.read()
    
    if len(content) < 500:
        print(f"WARNING: {filepath} seems unusually short ({len(content)} chars). Potential truncation?")
        
    missing = [k for k in required_keywords if k not in content]
    if missing:
        print(f"ERROR: {filepath} is missing critical headers: {missing}")
        sys.exit(1)
    
    print(f"SUCCESS: {filepath} integrity verified.")

def main():
    discovery_keywords = [
        "DISCOVERY CHECKLIST",
        "DESTINATION SOVEREIGNTY",
        "CONTEXT ISOLATION",
        "PHASE-GATE",
        "HARD BANS",
        "narrate"
    ]
    
    builder_keywords = [
        "CLIMATE SAFETY",
        "WEATHER GUARD",
        "SILENT BUILD PROTOCOL",
        "MANDATORY SPEECH",
        "ONE-STEP BOOKING",
        "ITINERARY LOGIC",
        "propose_itinerary_batch_bound"
    ]
    
    check_prompt_file("prompts/discovery_prompt.md", discovery_keywords)
    check_prompt_file("prompts/builder_prompt.md", builder_keywords)

if __name__ == "__main__":
    main()
