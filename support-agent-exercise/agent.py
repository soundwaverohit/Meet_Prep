"""
Support Concierge Agent -- practice exercise.
Nimbus Cloud Storage needs a support agent that holds a REAL conversation:
it remembers what's already been discussed, decides whether to search the
knowledge base, check an account, ask a clarifying question, or hand off
to a human -- and never opens a ticket or escalates without asking first.

tools.py is complete. Your job is entirely in this file:
  1. Write the system prompt from data/support_policy.md.
  2. Build the per-turn tool-calling loop (you've done this shape twice now).
  3. Make the conversation persist across multiple user turns -- this is
     the new part. Nothing here should reset `messages` between inputs.

See README.md for the full problem statement and five example
conversations to run once you're done.
"""

import anthropic
from dotenv import load_dotenv

# Importing the schemas + helpers from tools.py -- everything on the
# right is already implemented there; you're only writing code in THIS
# file (see reference-agent/stage3_multi_turn_with_tools.py for the loop
# shape these pieces plug into).
from tools import (
    SEARCH_KNOWLEDGE_BASE_SCHEMA,
    CHECK_ACCOUNT_SCHEMA,
    CREATE_SUPPORT_TICKET_SCHEMA,
    ESCALATE_TO_HUMAN_SCHEMA,
    dispatch,
    extract_text,
)

load_dotenv()   # reads ANTHROPIC_API_KEY out of .env into the environment

client = anthropic.Anthropic()
MODEL = "claude-sonnet-5"
MAX_STEPS = 8   # safety cap on how many tool-call rounds a single turn may take before giving up

# The four schemas imported above, collected into the list that gets
# passed to messages.create(tools=TOOLS) -- this is what tells Claude
# which tools exist and how to call them.
TOOLS = [
    SEARCH_KNOWLEDGE_BASE_SCHEMA,
    CHECK_ACCOUNT_SCHEMA,
    CREATE_SUPPORT_TICKET_SCHEMA,
    ESCALATE_TO_HUMAN_SCHEMA,
]

# TODO (Stage 1): Read data/support_policy.md and write a system prompt that
#   encodes its rules -- not just "you are a support agent" but the actual
#   decision logic: when to search the KB vs check the account, why a
#   security mention skips straight to escalation, why tickets/escalations
#   need customer confirmation first, and the refund threshold. The model
#   only knows these rules if you put them in the prompt -- the policy file
#   is never sent automatically. Use XML tags (<role>, <policy>, etc.) like
#   Week 3's persona_agent.py did.
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
    "1. SECURITY OVERRIDES EVERYTHING -- check this rule before any other. A "
    "security signal is ANY of: a suspicious or unexpected login, an unrecognized "
    "device, an account locked that the customer did NOT lock themselves, or the "
    "customer saying anything like 'I think someone else has access' / 'someone got "
    "into my account'. The moment you detect one, call escalate_to_human "
    "IMMEDIATELY on this same turn. Do NOT search_knowledge_base first, do NOT "
    "check_account first, and do NOT ask the customer to confirm first -- security "
    "skips the queue and skips the Rule 5 confirmation step entirely. After "
    "escalating, tell the customer what you just did and why. If a message mixes a "
    "security concern with any other request, handle the security escalation first "
    "and address the rest only afterward.\n"
    "2. Identify the customer before touching account-specific data. Never call "
    "check_account until the customer has given an email address. If a request "
    "needs account data (storage usage, billing status, or plan tier) and you don't "
    "have an email yet, ask for it -- never guess the email and never assume a plan "
    "tier.\n"
    "3. Try the knowledge base first for generic issues. For password resets, "
    "general 'how do I...' questions, and first-time reports of sync trouble, call "
    "search_knowledge_base BEFORE check_account -- most of these need no "
    "account-specific data at all.\n"
    "4. Never repeat a troubleshooting step the customer already tried. If they say "
    "a fix didn't work, do not suggest that fix again or restate the same KB steps. "
    "Move to the next tier: if the KB has no further steps, or they've already "
    "tried everything in the Sync Issues article, escalate to a human engineer "
    "instead of looping on the same advice.\n"
    "5. Tickets and escalations ALWAYS require confirmation first. Never call "
    "create_support_ticket or escalate_to_human without first telling the customer "
    "exactly what you're about to do and getting a clear 'yes' / 'go ahead' / "
    "equivalent in their NEXT message. The ONLY exception is Rule 1 (security), "
    "which escalates immediately and explains afterward.\n"
    "6. Refunds. A refund under $50 for a clearly accidental or duplicate charge "
    "may be described as 'processed' without a ticket. A refund of $50 or more "
    "ALWAYS requires create_support_ticket with priority 'high' and a note that "
    "billing-team approval is needed -- never tell the customer a refund of $50+ is "
    "approved yourself.\n"
    "7. Storage-limit complaints are not bugs. If a customer is upset about hitting "
    "their storage limit, explain the plan limits and upgrade path from the "
    "knowledge base -- this is expected behavior, so do NOT create a ticket or "
    "apologize as if something is broken. The one exception: if the customer "
    "explicitly disputes their actual usage number, call check_account to verify it "
    "first.\n"
    "</policy>"
)



def run_turn(messages: list[dict], user_msg: str) -> str:
    """
    Handle one user message against the given conversation history.

    TODO (Stage 2): append user_msg to `messages` as a user turn, then loop:
      - call client.messages.create(model=MODEL, max_tokens=1024,
        system=SYSTEM, tools=TOOLS, messages=messages)
      - append resp.content to `messages` as the assistant turn
      - if resp.stop_reason != "tool_use": return the text (extract_text
        handles pulling it out) and stop
      - otherwise, run every tool_use block in resp.content through
        dispatch(), collect ALL results into one list of tool_result
        blocks, append that as a single user message, and loop again
        (respect MAX_STEPS, same guardrail as Week 2 Stage 4)
    This is the same loop shape as Week 2 Stage 4 / the loan exercise --
    the difference this time is `messages` is passed in from OUTSIDE the
    function instead of being created fresh here.
    """
    messages.append({"role": "user", "content": user_msg})  # mutate the SAME list the caller passed in

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


if __name__ == "__main__":
    # TODO (Stage 3): this is the actual Week 3 skill. `messages` must be
    #   created ONCE, here, before the loop starts -- and every call to
    #   run_turn() must reuse and mutate the SAME list, so the agent
    #   remembers earlier turns (an email you gave it, a fix it already
    #   suggested, an account it already looked up). If you create a new
    #   `messages = []` inside run_turn() or inside this loop, you've
    #   rebuilt the Week 2 agent, not a Week 3 one -- test this with
    #   conversation 2 in README.md, which only works if the agent
    #   remembers what it suggested one turn ago.
    messages: list[dict] = []   # created once, outside the while loop -- do not move this line inside it
    while True:
        user_msg = input("> ")
        print(run_turn(messages, user_msg))
