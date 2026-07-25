"""
Stage 2 -- The fix: a multi-turn loop.
The only change from Stage 1: `messages` is created ONCE, before the
REPL loop starts, and every call appends to and reuses that SAME list --
both the user's message and the model's reply. That's the entire
mechanic behind "multi-turn conversation." No tools, no summarization,
no persona -- just state that survives across calls.

Run:  python stage2_multi_turn.py
Try:  "My name is Jordan."  then  "What's my name?" -- now it remembers.
"""

import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic()
MODEL = "claude-sonnet-5"
SYSTEM = "You are a helpful assistant."


def run_agent(messages: list[dict], user_msg: str) -> str:
    # `messages` is passed IN from the caller instead of being created
    # here -- that's the whole difference from Stage 1. Whatever this
    # list already contains (from earlier turns) is still there.

    # 1. Append the new user turn to the EXISTING list (not a fresh one).
    #    Python lists are mutable and passed by reference, so this
    #    .append() modifies the same list object the caller holds --
    #    there's no need to return it or reassign anything.
    messages.append({"role": "user", "content": user_msg})

    resp = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM,
        messages=messages,   # sends the FULL history so far, not just this one message
    )
    text = next((b.text for b in resp.content if b.type == "text"), "")

    # 2. Append the assistant's reply too -- the model needs to see its
    #    own prior turns on the NEXT call, not just the human's, or the
    #    conversation reads as disconnected fragments to it. Skipping
    #    this line is the single most common way to accidentally rebuild
    #    Stage 1's bug while thinking you fixed it.
    messages.append({"role": "assistant", "content": text})
    return text


if __name__ == "__main__":
    # 3. Created ONCE, outside the loop, before any input is read. Every
    #    run_agent() call below receives and mutates this SAME list --
    #    that object identity is what makes state persist across turns.
    #    If you moved this line inside the while loop, you'd be back to
    #    Stage 1's bug: a fresh empty list every iteration.
    messages: list[dict] = []
    while True:
        user_msg = input("> ")
        print(run_agent(messages, user_msg))
