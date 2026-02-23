# Agent Engineering & Discovery Guidelines

This document serves as the primary reference for AI assistants working on the `google_adk_voice_bot`. It outlines critical architectural decisions and discovery protocols that MUST be maintained.

## 1. Smart Context Management (The "Sandwich" Strategy)
To combat context "drowning" and primacy/recency bias in long-running sessions:
- **Instruction Sandwiching**: Critical "Hard Bans" and Discovery Mandates must be placed at both the **TOP** and **BOTTOM** of the system prompt.
- **Context Pruning**: The `global_context` (historical packages) must be pruned. Currently, we limit detailed itemization to the **10 most recent packages**. Older packages are collapsed into titles only.
- **Lost in the Middle**: Always keep the "middle" of the prompt reserved for data (About Me, Package Views) and the "edges" for strict behavioral mandates.

## 2. Discovery Protocols (Level 6 & 7)
The agent acts as a **Consultant-First** expert, not a menu.

### Phase Hierarchy (L6)
You MUST resolve requirements in this strict order:
1.  **Phase 1: Logistics**: Resolve Origin, Departure Date, and Duration.
2.  **Phase 2: Economy**: Resolve Budget inquiry (e.g., "What kind of investment...?").
3.  **Phase 3: Vision**: Ask broad, open-ended experiential questions (Style, Vibe, Pace).
4.  **Phase 4: Selection**: Internally select destinations; never ask the user "Where?".

### Hard Constraints
- **The "Where" Ban**: NEVER ask the user for a destination preference, city name, or region.
- **Absolute Anonymity**: NEVER name any specific location, hotel, or activity until the final Itinerary Reveal via `[NAVIGATE_TO_PACKAGE]`.
- **Day 1 Reset (L7)**: Every new surprise itinerary MUST start at Day 1, regardless of existing historical packages.
- **Sequential Build**: Move directly to the *nature* of the next item (Day 1, then Day 2) once vision is resolved.

## 3. Retrieval Architecture
- **Agentic Retrieval over RAG**: We prioritize letting the agent use tools (`list_all_packages`, `find_packages`) to find specific historical data rather than massive semantic context injection (RAG). 
- **Tool Discipline**: Tools should be called **SILENTLY**. No narration like "I am searching..." or "I have added...".

## 4. UI Protocols
- **Choice Buttons**: Always use `[RESPONSE_OPTIONS: ["Option 1", "Option 2"]]` for conversational branches.
- **Brevity**: Responses must be extremely concise and verbal-friendly.
- **Sentence Integrity**: Every response must start with a fresh, complete sentence. No acknowledgement crumbs like "Got it" or "Okay" if they lead to fragments.
