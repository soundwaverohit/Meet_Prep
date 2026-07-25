"""
Multi-Turn Internship Finder -- `messages` persists across every turn.
Identical tools, system prompt, and model to stateless_agent.py. The
ONLY code difference: `messages` is created once in __main__ (or passed
in by run_demo.py) and reused/mutated across calls, instead of rebuilt
inside run_agent() every time. That single difference is what lets this
agent actually improve its recommendations turn over turn, instead of
re-asking the same questions or contradicting itself.

Run:  python multi_turn_agent.py
"""

import anthropic                 # the official Anthropic Python SDK
from dotenv import load_dotenv   # reads key=value pairs from .env into environment variables

from tools import (               # our own tools.py, in the same directory
    SEARCH_INTERNSHIPS_SCHEMA,
    GET_INTERNSHIP_DETAILS_SCHEMA,
    TRACK_STATUS_SCHEMA,
    LIST_TRACKED_SCHEMA,
    dispatch,
    extract_text,
)

load_dotenv()  # loads ANTHROPIC_API_KEY from .env into the environment

client = anthropic.Anthropic()  # the API client -- reads the key from the environment automatically
MODEL = "claude-sonnet-5"        # which model every request in this file uses
MAX_STEPS = 6   # safety cap on tool-call rounds within a single call to run_agent()

TOOLS = [                         # the tool schemas passed to every messages.create() call below
    SEARCH_INTERNSHIPS_SCHEMA,
    GET_INTERNSHIP_DETAILS_SCHEMA,
    TRACK_STATUS_SCHEMA,
    LIST_TRACKED_SCHEMA,
]

# Same system prompt, word for word, as stateless_agent.py -- keeping it
# identical means any behavioral difference we observe comes from
# messages-persistence, not from a better-written prompt.
SYSTEM = (
    "You are an internship search assistant. Use search_internships to find "
    "matching listings, get_internship_details for more on a specific one, "
    "and track_status to record a candidate's decision (shortlisted / applied "
    "/ rejected / not_interested) whenever they make one. Pay attention to "
    "every preference the candidate states -- location, pay, remote/onsite, "
    "mentorship, company exclusions -- and factor ALL of them into your "
    "recommendations, not just the most recent message. When asked to "
    "summarize or prioritize, base it on everything discussed so far."
)


def run_agent(messages: list[dict], user_msg: str) -> str:
    # THE VARIABLE UNDER TEST: `messages` is a parameter, not a local --
    # whatever preferences, search results, and tracked statuses are
    # already in it from EARLIER calls are still there when this call
    # starts. This is the entire difference from stateless_agent.py, and
    # it's what makes the system prompt's "factor in everything discussed
    # so far" instruction actually achievable.
    messages.append({"role": "user", "content": user_msg})  # adds onto the SAME list the caller passed in, doesn't replace it

    for _ in range(MAX_STEPS):  # keep chasing tool calls until a final answer or MAX_STEPS is hit
        resp = client.messages.create(  # sends the FULL accumulated history, not just this one message
            model=MODEL, max_tokens=1024, system=SYSTEM, tools=TOOLS, messages=messages,
        )
        messages.append({"role": "assistant", "content": resp.content})  # record this response before handling it

        if resp.stop_reason != "tool_use":  # the model answered directly instead of requesting a tool
            return extract_text(resp)  # pull the text out and stop looping

        tool_results = []  # one tool_result entry per tool_use block in this response
        for block in resp.content:  # walk every content block in the response
            if block.type == "tool_use":  # only handle tool_use blocks; ignore any text alongside them
                result = dispatch(block.name, block.input)  # actually execute the requested tool
                tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})  # link result to its request
        messages.append({"role": "user", "content": tool_results})  # send all results back as one turn, then loop again

    return "[stopped: hit MAX_STEPS]"  # safety valve if it never stops asking for tools


if __name__ == "__main__":  # only runs when this file is executed directly, not when imported
    messages: list[dict] = []   # created once, mutated every turn -- this is the entire fix
    while True:  # infinite loop -- keeps prompting until Ctrl+C
        user_msg = input("> ")  # blocks until the user types something and presses Enter
        print(run_agent(messages, user_msg))  # same `messages` object passed in on every iteration
