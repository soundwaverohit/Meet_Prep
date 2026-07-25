#!/usr/bin/env python3
"""
Test the support agent against the 5 example conversations from README.md
"""

import sys
from io import StringIO
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
   again or restate the same knowledge-base steps. Move to the next tier:
   if the KB has no further steps, or the customer has already tried
   everything in the relevant KB section (e.g. sync issues), propose
   escalating to a human engineer and ask for confirmation first (Rule 5).

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
- escalate_to_human: security (immediately, no confirmation) or when KB
  steps are exhausted and the issue is still unresolved (after confirmation).
</tool_usage>

<conversation>
Remember the full conversation. A plain "thanks" or acknowledgment does not
need a tool call. Do not re-lookup or re-suggest things already resolved or
already tried in earlier turns.
</conversation>"""


def run_turn(messages: list[dict], user_msg: str) -> str:
    """Handle one user message against the given conversation history."""
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


def test_conversation(name: str, turns: list[str]):
    """Run a test conversation and print results."""
    print(f"\n{'='*70}")
    print(f"TEST: {name}")
    print(f"{'='*70}")

    messages = []
    for i, user_msg in enumerate(turns, 1):
        print(f"\nTurn {i}:")
        print(f"USER: {user_msg}")
        response = run_turn(messages, user_msg)
        print(f"AGENT: {response}")


if __name__ == "__main__":
    # Test 1: Knowledge-base only, no account needed
    test_conversation(
        "1. Knowledge-base only, no account needed",
        [
            "Hi, I forgot how to reset my password",
            "Thanks, that worked!",
        ]
    )

    # Test 2: Memory + escalation (the core Week 3 test)
    test_conversation(
        "2. Memory + escalation (the core Week 3 test)",
        [
            "My files aren't syncing",
            "I already tried restarting the app and clearing the cache, still broken",
            "yes please escalate it",
        ]
    )

    # Test 3: Security skips the queue
    test_conversation(
        "3. Security skips the queue",
        [
            "I think someone else logged into my account, I don't recognize this device",
        ]
    )

    # Test 4: Refund threshold
    test_conversation(
        "4. Refund threshold",
        [
            "My last charge of $89 was a mistake, can I get a refund? My email is carol@example.com",
            "yes go ahead and open the ticket",
        ]
    )

    # Test 5: Ask before guessing
    test_conversation(
        "5. Ask before guessing",
        [
            "How much storage do I have left?",
            "alice@example.com",
        ]
    )

    print(f"\n{'='*70}")
    print("All tests completed!")
    print(f"{'='*70}")
