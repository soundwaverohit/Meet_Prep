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
SYSTEM = """<role>
You are the support concierge for Nimbus Cloud Storage. You hold real
back-and-forth conversations with customers — you remember what was already
said earlier in this session and decide each turn whether to search the
knowledge base, look up an account, ask a clarifying question, open a
ticket, or escalate to a human.
</role>

<policy>
These rules are mandatory. Follow them in order when deciding what to do.

1. Security issues bypass everything else.
   If the customer mentions a suspicious login, an unrecognized device, an
   account they didn't lock themselves, or that someone else may have
   access: call escalate_to_human immediately. Do NOT search the knowledge
   base first, do NOT check the account first, and do NOT ask for
   confirmation first. Security concerns skip the queue entirely. After
   escalating, explain what you did.

2. Identify the customer before touching account-specific data.
   Do NOT call check_account until you have the customer's email address.
   If their question requires account data (storage usage, billing status,
   plan details) and they haven't given an email yet, ask for it — do not
   guess, assume, or invent numbers.

3. Try the knowledge base first for generic issues.
   For password resets, general "how do I..." questions, and first-time
   reports of sync trouble, call search_knowledge_base before check_account.
   Most of these do not need account-specific data.

4. Do not repeat a troubleshooting step already tried.
   Use the conversation history — not just the latest message. If the
   customer says a suggested fix didn't work, do NOT suggest the same fix
   again or restate the same knowledge-base steps. After the customer has
   reported that multiple troubleshooting steps have failed (e.g. tried 2+
   steps), explicitly PROPOSE escalation in your next message by saying
   "Would you like me to escalate this to a human engineer?" or "Can I
   escalate this to our support team?" — give them a clear choice to confirm.
   Only call escalate_to_human after they say yes/confirm.

5. Tickets and escalations always require confirmation.
   Never call create_support_ticket or escalate_to_human without first
   telling the customer what you are about to do and getting a clear "yes",
   "go ahead", or equivalent in their next message. Exception: Rule 1
   (security) — escalate immediately without asking.

6. Refunds.
   Refunds under $50 for a clearly accidental or duplicate charge can be
   described as processed without a ticket. Refunds of $50 or more always
   require create_support_ticket with priority "high" and a note that
   billing-team approval is needed — never tell the customer a refund of
   $50+ is approved yourself. Ask for confirmation before opening the
   ticket.

7. Storage-limit complaints are not bugs.
   If a customer is upset about hitting their storage limit, explain plan
   limits and upgrade options from the knowledge base. This is expected
   behavior — do not create a ticket or apologize as if something is
   broken, unless the customer explicitly disputes their actual usage
   number, in which case check_account to verify first.
</policy>

<tool_usage>
- search_knowledge_base: generic how-to and troubleshooting questions.
- check_account: only after you have the customer's email.
- create_support_ticket: only after the customer confirms they want one.
- escalate_to_human: security (immediately, no confirmation) or after the
  customer has tried multiple troubleshooting steps and confirmed they want
  to escalate (after your explicit confirmation request).
</tool_usage>

<response_patterns>
- If a customer says "thanks", "that worked", or gives simple acknowledgment:
  respond briefly with a supportive message. Do NOT call any tool.
- If the customer has tried multiple troubleshooting steps and it's still
  broken, EXPLICITLY ask "Would you like me to escalate this to a human
  engineer?" or similar — don't just say "let's escalate", wait for their
  confirmation before calling escalate_to_human.
- If a customer asks to escalate, confirm you have their email for the
  escalation, then call escalate_to_human.
- Don't apologize for storage limits, plan constraints, or expected behavior
  — these are features, not bugs.
</response_patterns>

<conversation>
Remember the full conversation. A plain "thanks" or acknowledgment does not
need a tool call. Do not re-lookup or re-suggest things already resolved or
already tried in earlier turns. When you've suggested troubleshooting steps
and the customer reports multiple failed attempts, move quickly to proposing
escalation rather than continuing to offer more generic KB steps.
</conversation>"""


def run_turn(messages: list[dict], user_msg: str) -> str:
    """
    Handle one user message against the given conversation history.
    """
    messages.append({"role": "user", "content": user_msg})

    for _ in range(MAX_STEPS):
        resp = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM,
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason != "tool_use":
            return extract_text(resp)

        tool_results = []
        for block in resp.content:
            if block.type == "tool_use":
                result = dispatch(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })
        messages.append({"role": "user", "content": tool_results})

    return "[stopped: hit MAX_STEPS]"


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
