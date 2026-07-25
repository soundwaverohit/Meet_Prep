"""
Stage 1 -- The problem: a stateless agent.
Same shape as Week 2's agent.py -- run_agent() builds a brand-new
`messages` list on every call. Run this, tell it your name, then ask
"what's my name?" in the next input. It won't know -- there's no state
connecting one call to the next, even though it's the same REPL session.

Run:  python stage1_stateless.py
Try:  "My name is Jordan."  then  "What's my name?"
"""

import anthropic                 # the official Anthropic SDK -- gives us the Anthropic client class
from dotenv import load_dotenv   # reads key=value pairs from a .env file into environment variables

load_dotenv()  # loads ANTHROPIC_API_KEY from .env into the environment so Anthropic() can find it automatically

client = anthropic.Anthropic()          # the API client; reads ANTHROPIC_API_KEY from the environment
MODEL = "claude-sonnet-5"               # which model every messages.create() call below will use
SYSTEM = "You are a helpful assistant." # system prompt: instructions sent every request, not part of the visible conversation


def run_agent(user_msg: str) -> str:
    # THE BUG, on purpose: this list is created fresh, INSIDE this
    # function, every single time run_agent() is called. Nothing from a
    # previous call survives here -- the model sees only this one
    # message, as if the conversation just started.
    messages = [{"role": "user", "content": user_msg}]

    resp = client.messages.create(  # sends one request to the API and blocks until the full reply arrives
        model=MODEL,                # which model answers this request
        max_tokens=1024,            # hard cap on how many tokens the reply may contain
        system=SYSTEM,              # the system prompt defined above
        messages=messages,          # the (single-message) conversation history sent on this call
    )

    # resp.content is a list of content blocks (text, tool_use, etc.).
    # We only care about the first text block, so scan for it and fall
    # back to "" if for some reason there isn't one.
    return next((b.text for b in resp.content if b.type == "text"), "")


if __name__ == "__main__":       # only runs when this file is executed directly, not when imported
    while True:                          # infinite loop -- keeps prompting until you Ctrl+C
        user_msg = input("> ")           # blocks until you type something and press Enter
        print(run_agent(user_msg))       # each call is fully independent -- see the bug above
