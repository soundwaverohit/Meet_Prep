"""
Kitchen Sink Agent -- ONE agent, ALL 7 tools across 3 unrelated domains
(support, internship search, arithmetic), ONE merged system prompt
trying to cover all three policies at once. This is the "too many
tools, too much context" side of the comparison -- see
orchestrator_agent.py for the alternative, and compare.py to test them
head to head.

Run:  python kitchen_sink_agent.py
"""

import anthropic
from dotenv import load_dotenv

from tools import ALL_TOOLS, dispatch, extract_text

load_dotenv()

client = anthropic.Anthropic()
MODEL = "claude-sonnet-5"
MAX_STEPS = 8

TOOLS = ALL_TOOLS   # all 7, sent on EVERY request, regardless of what's actually being asked

# One prompt holding three unrelated policies at once. Nobody sits down
# and writes "let's make our agent worse" -- this is how tool bloat
# actually happens in practice: one merged prompt accumulates as more
# capabilities get bolted onto the same agent over time.
SYSTEM = (
    "You are a general assistant for Nimbus Cloud Storage with three "
    "unrelated capabilities: customer support, internship search, and "
    "arithmetic.\n\n"
    "SUPPORT: search_knowledge_base for generic issues; check_account "
    "only once you have an email; security mentions (suspicious login, "
    "unrecognized device) escalate immediately via escalate_to_human, no "
    "confirmation needed; anything else needing create_support_ticket or "
    "escalate_to_human needs the customer to confirm first; refunds "
    "under $50 can be described as processed, $50+ needs a ticket with "
    "priority high.\n\n"
    "INTERNSHIPS: use search_internships to find saved listings, "
    "track_status to record or check a candidate's status on a specific "
    "internship ID.\n\n"
    "MATH: use calculator for arithmetic.\n\n"
    "Use whichever tool fits the request."
)


def run_agent(messages: list[dict], user_msg: str) -> tuple[str, int, list[str]]:
    """Returns (reply_text, total_input_tokens_this_call, [tool names called])."""
    messages.append({"role": "user", "content": user_msg})
    total_input_tokens = 0
    called: list[str] = []

    for _ in range(MAX_STEPS):
        resp = client.messages.create(
            model=MODEL, max_tokens=1024, system=SYSTEM, tools=TOOLS, messages=messages,
        )
        total_input_tokens += resp.usage.input_tokens   # includes all 7 tool schemas + the merged prompt, every call
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

    return "[stopped: hit MAX_STEPS]", total_input_tokens, called


if __name__ == "__main__":
    messages: list[dict] = []
    while True:
        user_msg = input("> ")
        reply, tokens, called = run_agent(messages, user_msg)
        print(reply)
        print(f"[tools called: {called or 'none'} | input tokens: {tokens}]")
