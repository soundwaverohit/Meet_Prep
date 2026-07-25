# Reference — Multi-Turn Conversation Loop

Staged, worked examples (not an exercise) isolating the "loop messages"
mechanic on its own, before it gets combined with tools, summarization,
or a persona. Run each one and try the prompt in its docstring.

| Stage | File | What it adds |
|---|---|---|
| 1 | `stage1_stateless.py` | The problem: `messages` rebuilt every call (same bug as Week 2's `agent.py`). Ask its name, then ask again -- it won't know. |
| 2 | `stage2_multi_turn.py` | The fix: `messages` created once in `__main__`, passed into every call, mutated (not replaced) each turn. This alone is "multi-turn conversation." |
| 3 | `stage3_multi_turn_with_tools.py` | Nests the Week 2 per-turn tool loop inside the Stage 2 cross-turn loop -- two loops, two different jobs, working together. This is the exact shape used in `../support-agent-exercise/agent.py`. |

## Where this connects to the rest of Week 3

- **`../memory.py`** and **`../persona_agent.py`** take Stage 2's plain
  `messages` list and add the next layer on top: once the conversation
  gets long, summarize older turns instead of resending them forever.
  That's an optimization on Stage 2, not a replacement for it -- you
  still need Stage 2's mechanic underneath any summarization.
- **`../support-agent-exercise/`** is Stage 3 with real tools and a
  decision policy, for you to build yourself.

## The one-sentence version

A "multi-turn agent" is not a different kind of API call -- it's the same
`client.messages.create()` from Week 2, called repeatedly against a
`messages` list that lives *outside* the function and gets appended to,
never replaced.
