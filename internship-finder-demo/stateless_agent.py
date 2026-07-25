"""
Stateless Internship Finder -- rebuilds `messages` on every call.
Same tools, same system prompt, same model as multi_turn_agent.py -- the
ONLY difference between this file and that one is whether `messages`
persists across turns. Run the same 5-turn script (README.md, or just
run_demo.py) against both and compare.

Run:  python stateless_agent.py
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

# Word-for-word identical to multi_turn_agent.py's SYSTEM -- keeping the
# prompt fixed isolates messages-persistence as the ONLY variable in this
# comparison. Note it explicitly asks the model to remember prior
# preferences -- that instruction alone cannot work here, because those
# prior turns are never actually in the request (see run_agent below).
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


def run_agent(user_msg: str) -> str:
    # THE VARIABLE UNDER TEST: a brand-new list, scoped to this function
    # call only. Whatever was said in a PREVIOUS call to run_agent() is
    # gone -- it was never written anywhere this call can see. The system
    # prompt's instruction to "factor in everything discussed so far" is
    # a promise the code cannot keep, because "so far" is empty every time.
    messages = [{"role": "user", "content": user_msg}]  # a fresh one-message list, every single call

    for _ in range(MAX_STEPS):  # keep chasing tool calls until a final answer or MAX_STEPS is hit
        resp = client.messages.create(  # sends the request, blocks until the full response arrives
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
    while True:  # infinite loop -- keeps prompting until Ctrl+C
        user_msg = input("> ")  # blocks until the user types something and presses Enter
        print(run_agent(user_msg))   # note: no shared `messages` variable anywhere in this loop
