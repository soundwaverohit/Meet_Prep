"""
Live Internship Search Agent.
Extends the multi-turn pattern from ../internship-finder-demo/ with a
REAL capability: it can go out to the actual internet (via Anthropic's
built-in web_search tool) and permanently save what it finds into
data/internships.json -- but ONLY when you explicitly ask it to search,
not on every mention of internships. See README.md for the policy and
an annotated example run.

Run:  python agent.py
"""

import anthropic                 # the official Anthropic Python SDK
from dotenv import load_dotenv   # reads key=value pairs from .env into environment variables

from tools import (               # our own tools.py, in the same directory
    SEARCH_SAVED_INTERNSHIPS_SCHEMA,
    SAVE_INTERNSHIP_SCHEMA,
    LIST_SAVED_INTERNSHIPS_SCHEMA,
    dispatch,
    extract_text,
)

load_dotenv()  # loads ANTHROPIC_API_KEY from .env into the environment

client = anthropic.Anthropic()  # the API client -- reads the key from the environment automatically
MODEL = "claude-sonnet-5"        # which model every request uses
MAX_STEPS = 8   # a bit higher than the demo's cap -- a real web search + several saves can take more rounds

# Anthropic's own BUILT-IN tool -- declaring it here is enough. Claude
# decides to call it, and ANTHROPIC'S OWN SERVERS run the actual search
# and return results as content blocks in the SAME response. There is no
# Python function anywhere for "web_search" -- unlike our three custom
# tools in tools.py, we never execute this one ourselves.
WEB_SEARCH_TOOL = {
    "type": "web_search_20260209",   # the specific built-in tool version
    "name": "web_search",             # the name Claude uses to invoke it
    "max_uses": 5,                    # hard cap so one request can't trigger unlimited live searches
}

TOOLS = [                          # everything Claude can call this session
    WEB_SEARCH_TOOL,                # built-in, server-executed
    SEARCH_SAVED_INTERNSHIPS_SCHEMA,   # ours, client-executed
    SAVE_INTERNSHIP_SCHEMA,            # ours, client-executed
    LIST_SAVED_INTERNSHIPS_SCHEMA,     # ours, client-executed
]

# The decision policy lives here, in the system prompt -- exactly like
# the support-agent-exercise's confirmation rules. Nothing in the tool
# definitions themselves stops the model from web-searching on every
# turn; this prompt is the only thing that gates it.
SYSTEM = (
    "You help a candidate find and track real internships, backed by a "
    "growing local file of listings you've found (data/internships.json).\n\n"
    "<tools>\n"
    "- web_search: searches the live internet.\n"
    "- save_internship: permanently saves ONE real listing you found via "
    "web_search into the local file.\n"
    "- search_saved_internships / list_saved_internships: look at what's "
    "ALREADY saved locally -- free, instant, no internet.\n"
    "</tools>\n\n"
    "<policy>\n"
    "Only call web_search when the candidate explicitly asks you to SEARCH "
    "for internships (e.g. 'search for...', 'look up...', 'find real "
    "listings for...'). For anything else -- general questions, follow-ups "
    "about results you already found, 'show me the remote ones', 'what did "
    "we save earlier' -- use search_saved_internships or "
    "list_saved_internships instead. Do not do a live web search just "
    "because internships came up in conversation.\n\n"
    "When you DO search the web: only call save_internship for listings "
    "that are real, specific, and currently open (a real company, a real "
    "role, a real posting) -- never invent one to fill out a request. Save "
    "every genuinely matching result you find, not just one. Always "
    "include the source_url from web_search in save_internship so the "
    "listing is traceable.\n"
    "</policy>"
)


def run_agent(messages: list[dict], user_msg: str) -> str:
    # Same cross-turn pattern as multi_turn_agent.py in the demo:
    # `messages` is a parameter, mutated across calls, never rebuilt.
    messages.append({"role": "user", "content": user_msg})

    for _ in range(MAX_STEPS):   # keep looping until a final answer or MAX_STEPS is hit
        resp = client.messages.create(
            model=MODEL, max_tokens=1536, system=SYSTEM, tools=TOOLS, messages=messages,
        )
        messages.append({"role": "assistant", "content": resp.content})   # record this turn before handling it

        if resp.stop_reason == "pause_turn":
            # A server-side web_search chain hit its OWN internal
            # iteration cap mid-turn (this is separate from our
            # MAX_STEPS, which counts our loop iterations, not
            # Anthropic's internal search rounds). The assistant
            # content just appended above already ends in the exact
            # shape the API needs to resume on its own -- so we loop
            # straight back to messages.create() with NO new user
            # message and NO tool_result. Anthropic's docs explicitly
            # warn against adding a "Continue." message here: the API
            # detects the trailing server-tool block itself and resumes.
            continue

        if resp.stop_reason != "tool_use":
            # A normal final answer (end_turn), or a length/token limit
            # -- either way, nothing left for us to execute.
            return extract_text(resp)

        # stop_reason == "tool_use": at least one of OUR client-side
        # tools (save_internship, search_saved_internships,
        # list_saved_internships) is pending. If Claude ALSO used
        # web_search this same turn, its results already arrived as
        # server_tool_use / web_search_tool_result blocks -- those are
        # ALREADY resolved by Anthropic, and their .type is NOT
        # "tool_use", so the loop below naturally skips them. We only
        # ever dispatch and reply to genuine tool_use blocks.
        tool_results = []
        for block in resp.content:                 # walk every content block in the response
            if block.type == "tool_use":            # only OUR tools reach this branch
                result = dispatch(block.name, block.input)   # actually run the requested tool
                tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
        messages.append({"role": "user", "content": tool_results})   # send results back, then loop again

    return "[stopped: hit MAX_STEPS]"   # safety valve


if __name__ == "__main__":
    messages: list[dict] = []   # created once, mutated every turn -- same pattern as the demo
    while True:
        user_msg = input("> ")
        print(run_agent(messages, user_msg))
