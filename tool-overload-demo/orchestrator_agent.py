"""
Orchestrator Agent -- a router with THREE tiny "delegate" tools, each of
which runs a FOCUSED specialist scoped to only its own domain's tools
and prompt. The orchestrator itself never sees support/internship/math
tool schemas directly -- it only knows "these three capabilities exist,
here's how to hand off to each." Compare against kitchen_sink_agent.py,
which holds all 7 tools + all 3 policies in one place at once.

Run:  python orchestrator_agent.py
"""

import anthropic
from dotenv import load_dotenv

from tools import SUPPORT_TOOLS, INTERNSHIP_TOOLS, CALCULATOR_TOOLS, dispatch, extract_text

load_dotenv()

client = anthropic.Anthropic()
MODEL = "claude-sonnet-5"
SPECIALIST_MAX_STEPS = 6
ORCHESTRATOR_MAX_STEPS = 4

# Each specialist gets ONLY its own domain's rules -- nothing to dilute,
# nothing irrelevant taking up space. Same policy CONTENT as the kitchen
# sink's merged prompt, just not sharing a prompt with two other domains.
SUPPORT_SYSTEM = (
    "You are a support agent for Nimbus Cloud Storage. Use "
    "search_knowledge_base for generic issues before check_account. "
    "Never call check_account without an email. Any security mention "
    "(suspicious login, unrecognized device) -> escalate_to_human "
    "IMMEDIATELY, no confirmation needed -- this overrides everything "
    "else. For anything else, never call create_support_ticket or "
    "escalate_to_human without the customer confirming first. Refunds "
    "under $50 can be described as processed without a ticket; $50+ "
    "always needs create_support_ticket with priority 'high'."
)

INTERNSHIP_SYSTEM = (
    "You help a candidate with internship search. Use search_internships "
    "to find listings, track_status to record or check a status on a "
    "specific internship ID."
)

CALCULATOR_SYSTEM = "You do arithmetic. Use the calculator tool for any calculation."


def _run_specialist(system: str, tools: list, request: str) -> tuple[str, int, list[str]]:
    """Runs ONE focused sub-agent for a single delegated request, scoped
    to only `tools` and `system`. Returns (final_text, input_tokens_used, [tool names called])."""
    messages = [{"role": "user", "content": request}]
    total_input_tokens = 0
    called: list[str] = []
    for _ in range(SPECIALIST_MAX_STEPS):
        resp = client.messages.create(
            model=MODEL, max_tokens=1024, system=system, tools=tools, messages=messages,
        )
        total_input_tokens += resp.usage.input_tokens   # only THIS specialist's small tool list + prompt
        messages.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason != "tool_use":
            return extract_text(resp), total_input_tokens, called
        tool_results = []
        for block in resp.content:
            if block.type == "tool_use":
                called.append(block.name)
                result = dispatch(block.name, block.input)
                tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
        messages.append({"role": "user", "content": tool_results})
    return "[specialist stopped: hit MAX_STEPS]", total_input_tokens, called


# The orchestrator's delegate tools are plain Python functions that run
# an ENTIRE focused sub-agent internally. Globals here carry the token
# cost and underlying tool calls of the LAST delegate invocation back up
# to run_agent(), since a tool's return value can only be a string.
_LAST_TOKENS = 0
_LAST_CALLS: list[str] = []


def delegate_to_support(request: str) -> str:
    global _LAST_TOKENS, _LAST_CALLS
    text, tokens, calls = _run_specialist(SUPPORT_SYSTEM, SUPPORT_TOOLS, request)
    _LAST_TOKENS, _LAST_CALLS = tokens, calls
    return text


def delegate_to_internship(request: str) -> str:
    global _LAST_TOKENS, _LAST_CALLS
    text, tokens, calls = _run_specialist(INTERNSHIP_SYSTEM, INTERNSHIP_TOOLS, request)
    _LAST_TOKENS, _LAST_CALLS = tokens, calls
    return text


def delegate_to_calculator(request: str) -> str:
    global _LAST_TOKENS, _LAST_CALLS
    text, tokens, calls = _run_specialist(CALCULATOR_SYSTEM, CALCULATOR_TOOLS, request)
    _LAST_TOKENS, _LAST_CALLS = tokens, calls
    return text


DELEGATE_TO_SUPPORT_SCHEMA = {
    "name": "delegate_to_support",
    "description": "Hand off a Nimbus customer-support request (account issues, tickets, security, billing) to the support specialist.",
    "input_schema": {
        "type": "object",
        "properties": {"request": {"type": "string", "description": "The customer's request, verbatim or summarized."}},
        "required": ["request"],
    },
}

DELEGATE_TO_INTERNSHIP_SCHEMA = {
    "name": "delegate_to_internship",
    "description": "Hand off an internship-search or application-tracking request to the internship specialist.",
    "input_schema": {
        "type": "object",
        "properties": {"request": {"type": "string"}},
        "required": ["request"],
    },
}

DELEGATE_TO_CALCULATOR_SCHEMA = {
    "name": "delegate_to_calculator",
    "description": "Hand off an arithmetic question to the calculator specialist.",
    "input_schema": {
        "type": "object",
        "properties": {"request": {"type": "string"}},
        "required": ["request"],
    },
}

# The orchestrator's OWN tool list -- just 3 tiny schemas, none of the
# support/internship/calculator tool schemas appear here at all.
ORCHESTRATOR_TOOLS = [DELEGATE_TO_SUPPORT_SCHEMA, DELEGATE_TO_INTERNSHIP_SCHEMA, DELEGATE_TO_CALCULATOR_SCHEMA]

ORCHESTRATOR_SYSTEM = (
    "You route each request to the right specialist by calling exactly "
    "one delegate tool: delegate_to_support for Nimbus account/ticket/"
    "security/billing issues, delegate_to_internship for internship "
    "search or status tracking, delegate_to_calculator for arithmetic. "
    "Pass along enough of the request (including any email, ID, or "
    "number mentioned) for the specialist to act without needing to ask "
    "again. Return the specialist's answer to the user."
)

_ORCHESTRATOR_DISPATCH = {
    "delegate_to_support": delegate_to_support,
    "delegate_to_internship": delegate_to_internship,
    "delegate_to_calculator": delegate_to_calculator,
}


def run_agent(messages: list[dict], user_msg: str) -> tuple[str, int, list[str]]:
    """Returns (reply_text, total_input_tokens ACROSS orchestrator + delegate calls, [underlying tool names called])."""
    messages.append({"role": "user", "content": user_msg})
    total_input_tokens = 0
    all_tool_calls: list[str] = []

    for _ in range(ORCHESTRATOR_MAX_STEPS):
        resp = client.messages.create(
            model=MODEL, max_tokens=1024, system=ORCHESTRATOR_SYSTEM, tools=ORCHESTRATOR_TOOLS, messages=messages,
        )
        total_input_tokens += resp.usage.input_tokens   # the orchestrator's OWN small call -- 3 tiny schemas only
        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason != "tool_use":
            return extract_text(resp), total_input_tokens, all_tool_calls

        tool_results = []
        for block in resp.content:
            if block.type == "tool_use":
                handler = _ORCHESTRATOR_DISPATCH[block.name]
                result = handler(**block.input)          # runs an entire focused specialist internally
                total_input_tokens += _LAST_TOKENS         # add the specialist's own tokens for a fair total
                all_tool_calls.extend(_LAST_CALLS)          # and its underlying tool calls, for comparison to kitchen sink
                tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
        messages.append({"role": "user", "content": tool_results})

    return "[stopped: hit MAX_STEPS]", total_input_tokens, all_tool_calls


if __name__ == "__main__":
    messages: list[dict] = []
    while True:
        user_msg = input("> ")
        reply, tokens, calls = run_agent(messages, user_msg)
        print(reply)
        print(f"[underlying tools used: {calls or 'none'} | total input tokens: {tokens}]")
