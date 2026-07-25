"""
Support Concierge Agent -- SOLVED reference implementation.
This is the completed version of ../support-agent-exercise/agent.py, for
comparison after you've written your own (or if you want a working
reference to test against). See explanation.md for a walkthrough of each
design decision and how it maps back to data/support_policy.md.

Run:  python agent.py
Automated checks:  python run_tests.py
"""

import anthropic
from dotenv import load_dotenv

from tools import (
    SEARCH_KNOWLEDGE_BASE_SCHEMA,
    CHECK_ACCOUNT_SCHEMA,
    CREATE_SUPPORT_TICKET_SCHEMA,
    ESCALATE_TO_HUMAN_SCHEMA,
    dispatch,
    extract_text,
)

load_dotenv()

client = anthropic.Anthropic()
MODEL = "claude-sonnet-5"
MAX_STEPS = 8

TOOLS = [
    SEARCH_KNOWLEDGE_BASE_SCHEMA,
    CHECK_ACCOUNT_SCHEMA,
    CREATE_SUPPORT_TICKET_SCHEMA,
    ESCALATE_TO_HUMAN_SCHEMA,
]

# Stage 1 solved: every numbered rule in data/support_policy.md is
# translated into the prompt explicitly -- Claude never reads that file
# itself, so anything not restated here doesn't exist as far as the
# model is concerned. XML tags separate "what tools exist" from "the
# rules for using them," the same structure persona_agent.py used for
# role/voice/format.
SYSTEM = (
    "<role>You are a support agent for Nimbus Cloud Storage.</role>\n"
    "<tools>\n"
    "- search_knowledge_base: generic help articles (password reset, sync issues, "
    "storage limits, data recovery, billing).\n"
    "- check_account: look up a customer's account by email (plan, storage usage, "
    "billing status).\n"
    "- create_support_ticket: open a ticket for a human to follow up on.\n"
    "- escalate_to_human: hand the conversation off to a human agent immediately.\n"
    "</tools>\n"
    "<policy>\n"
    "1. Security issues bypass everything else. Any mention of a suspicious login, "
    "an unrecognized device, or a locked-out account the customer didn't lock "
    "themselves -> call escalate_to_human IMMEDIATELY. Do not search the knowledge "
    "base first, do not check the account first, and do not ask for confirmation "
    "first.\n"
    "2. Don't call check_account until you have an email address. If the customer "
    "hasn't given one yet and the question needs account data, ask for it -- don't "
    "guess or assume a plan tier.\n"
    "3. For generic issues (password resets, general how-do-I questions, first-time "
    "sync reports), search_knowledge_base BEFORE check_account -- most don't need "
    "account data at all.\n"
    "4. Don't repeat a troubleshooting step the customer already said they tried. "
    "If the knowledge base has no further steps, or they've already tried "
    "everything in the Sync Issues article, escalate to a human instead of "
    "repeating the same advice.\n"
    "5. Never call create_support_ticket or escalate_to_human without first "
    "telling the customer what you're about to do and getting a clear yes/go-ahead "
    "in their NEXT message. The one exception is Rule 1 (security) -- escalate "
    "immediately, then explain what you did.\n"
    "6. Refunds under $50 for a clearly accidental or duplicate charge can be "
    "described as 'processed' without a ticket. Refunds of $50 or more ALWAYS "
    "require create_support_ticket with priority 'high' and a note that "
    "billing-team approval is needed -- never tell the customer a refund of $50+ "
    "is approved yourself.\n"
    "7. Storage-limit complaints are not bugs. Explain plan limits and the "
    "upgrade path from the knowledge base. Don't create a ticket or apologize as "
    "if something is broken, unless the customer explicitly disputes their actual "
    "usage number -- then check_account to verify it first.\n"
    "</policy>"
)


def run_turn(messages: list[dict], user_msg: str) -> str:
    # Stage 2 solved: the per-turn tool loop, same shape as
    # reference-agent/stage3_multi_turn_with_tools.py and every other
    # tool-using agent in this project.
    messages.append({"role": "user", "content": user_msg})   # add this turn onto the EXISTING history

    for _ in range(MAX_STEPS):
        resp = client.messages.create(
            model=MODEL, max_tokens=1024, system=SYSTEM, tools=TOOLS, messages=messages,
        )
        messages.append({"role": "assistant", "content": resp.content})   # record the response before acting on it

        if resp.stop_reason != "tool_use":
            return extract_text(resp)   # final answer -- nothing left to execute

        tool_results = []
        for block in resp.content:
            if block.type == "tool_use":
                result = dispatch(block.name, block.input)   # actually run the requested tool
                tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
        messages.append({"role": "user", "content": tool_results})   # send ALL results back as one turn, then loop

    return "[stopped: hit MAX_STEPS]"


if __name__ == "__main__":
    # Stage 3 solved: `messages` created ONCE, here, before the REPL
    # loop starts -- every call to run_turn() below reuses and mutates
    # this SAME list, which is what lets the agent remember an email
    # given three turns ago, or a fix it already suggested one turn ago.
    messages: list[dict] = []
    while True:
        user_msg = input("> ")
        print(run_turn(messages, user_msg))
