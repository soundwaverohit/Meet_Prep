"""
Automated behavioral tests for the SOLVED Support Concierge Agent.
Runs the 5 example conversations from ../support-agent-exercise/README.md
against agent.py in this directory and checks the tool-call decisions
described in ../support-agent-exercise/ANSWER_KEY.md -- programmatically,
instead of "read the transcript and compare by eye."

This makes REAL API calls (needs your key in .env) and checks LLM-driven
DECISIONS, which are not 100% deterministic like a normal unit test. An
occasional failure on a borderline check doesn't necessarily mean the
code is wrong -- re-run once; if it fails the same check consistently,
that's a real signal. See explanation.md for more on this.

Run:  python run_tests.py
"""

import agent
import tools

# ── call recording ──────────────────────────────────────────────────────
# We wrap tools.dispatch so every tool call still actually executes (the
# agent needs real results to keep reasoning correctly), but we ALSO
# record what was called and with what arguments, so the checks below
# can assert on DECISIONS made, not on parsing printed text.
_original_dispatch = tools.dispatch
CALL_LOG: list[tuple[str, dict]] = []


def _recording_dispatch(name: str, tool_input: dict) -> str:
    CALL_LOG.append((name, tool_input))       # record before executing
    return _original_dispatch(name, tool_input)   # then actually run it for real


# `from tools import dispatch` in agent.py bound a SEPARATE name,
# agent.dispatch, at import time -- patching tools.dispatch alone would
# NOT affect calls made inside agent.run_turn(), which calls its own
# module-level `dispatch`. Both names have to be repointed.
tools.dispatch = _recording_dispatch
agent.dispatch = _recording_dispatch


def run_turn_and_capture(messages: list[dict], user_msg: str) -> tuple[str, list[tuple[str, dict]]]:
    """Runs one turn, returns (reply text, [tool calls made during just this turn])."""
    start = len(CALL_LOG)                      # how many calls existed before this turn
    reply = agent.run_turn(messages, user_msg)  # the actual agent call -- may trigger 0+ tool calls
    this_turn_calls = CALL_LOG[start:]          # only the NEW calls, added during this turn
    return reply, this_turn_calls


def names(calls: list[tuple[str, dict]]) -> set[str]:
    """Just the tool names from a list of (name, input) tuples, as a set."""
    return {name for name, _ in calls}


# ── test bookkeeping ─────────────────────────────────────────────────────

_passed = 0
_failed = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  PASS  {label}")
    else:
        _failed += 1
        print(f"  FAIL  {label}" + (f"  ({detail})" if detail else ""))


def reset_ticket_state() -> None:
    # tools._TICKETS is in-memory and accumulates across every call in
    # this process -- clear it between conversations so ticket IDs and
    # "already escalated" state from one conversation don't leak into
    # the next. Reaching into a "private" (underscore-prefixed) module
    # attribute is fine in a test file; tools.py itself has no public
    # reset helper because the interactive exercise never needed one.
    tools._TICKETS.clear()


# ── Conversation 1: knowledge-base only ─────────────────────────────────

def test_conversation_1() -> None:
    print("\n--- Conversation 1: password reset (KB only, no account, no ticket) ---")
    reset_ticket_state()
    messages: list[dict] = []

    _, calls1 = run_turn_and_capture(messages, "Hi, I forgot how to reset my password")
    check("Turn 1 calls search_knowledge_base", "search_knowledge_base" in names(calls1))
    check("Turn 1 does NOT call create_support_ticket", "create_support_ticket" not in names(calls1))
    check("Turn 1 does NOT call escalate_to_human", "escalate_to_human" not in names(calls1))

    _, calls2 = run_turn_and_capture(messages, "Thanks, that worked!")
    check("Turn 2 makes no tool calls at all", len(calls2) == 0, f"got {names(calls2)}")


# ── Conversation 2: memory + escalation (the core test) ─────────────────

def test_conversation_2() -> None:
    print("\n--- Conversation 2: sync issue -> escalation (memory test) ---")
    reset_ticket_state()
    messages: list[dict] = []

    _, calls1 = run_turn_and_capture(messages, "My files aren't syncing")
    check("Turn 1 calls search_knowledge_base", "search_knowledge_base" in names(calls1))
    check("Turn 1 does NOT escalate yet", "escalate_to_human" not in names(calls1))

    _, calls2 = run_turn_and_capture(
        messages, "I already tried restarting the app and clearing the cache, still broken"
    )
    check(
        "Turn 2 does NOT escalate without confirmation (Rule 5)",
        "escalate_to_human" not in names(calls2),
        f"got {names(calls2)}",
    )

    _, calls3 = run_turn_and_capture(messages, "yes please escalate it")
    check("Turn 3 calls escalate_to_human after confirmation", "escalate_to_human" in names(calls3))


# ── Conversation 3: security skips the queue ─────────────────────────────

def test_conversation_3() -> None:
    print("\n--- Conversation 3: security -> immediate escalation, no confirmation ---")
    reset_ticket_state()
    messages: list[dict] = []

    _, calls1 = run_turn_and_capture(
        messages, "I think someone else logged into my account, I don't recognize this device"
    )
    check("Escalates immediately", "escalate_to_human" in names(calls1))
    check("Does NOT search the knowledge base first", "search_knowledge_base" not in names(calls1))
    check("Does NOT check the account first", "check_account" not in names(calls1))


# ── Conversation 4: refund threshold ─────────────────────────────────────

def test_conversation_4() -> None:
    print("\n--- Conversation 4: $89 refund -> ticket, not a promise ---")
    reset_ticket_state()
    messages: list[dict] = []

    _, calls1 = run_turn_and_capture(
        messages,
        "My last charge of $89 was a mistake, can I get a refund? My email is carol@example.com",
    )
    check(
        "Turn 1 does NOT create a ticket without confirmation",
        "create_support_ticket" not in names(calls1),
        f"got {names(calls1)}",
    )

    _, calls2 = run_turn_and_capture(messages, "yes go ahead and open the ticket")
    ticket_calls = [c for c in calls2 if c[0] == "create_support_ticket"]
    check("Turn 2 creates a ticket after confirmation", len(ticket_calls) > 0)
    if ticket_calls:
        priority = ticket_calls[0][1].get("priority")
        check(f"Ticket priority is 'high' (got '{priority}')", priority == "high")


# ── Conversation 5: ask before guessing ──────────────────────────────────

def test_conversation_5() -> None:
    print("\n--- Conversation 5: ask for email before checking account ---")
    reset_ticket_state()
    messages: list[dict] = []

    _, calls1 = run_turn_and_capture(messages, "How much storage do I have left?")
    check(
        "Turn 1 does NOT check an account without an email",
        "check_account" not in names(calls1),
        f"got {names(calls1)}",
    )

    _, calls2 = run_turn_and_capture(messages, "alice@example.com")
    account_calls = [c for c in calls2 if c[0] == "check_account"]
    check("Turn 2 checks the account once given the email", len(account_calls) > 0)
    if account_calls:
        email = account_calls[0][1].get("email")
        check(f"Looked up the right email (got '{email}')", email == "alice@example.com")


if __name__ == "__main__":
    test_conversation_1()
    test_conversation_2()
    test_conversation_3()
    test_conversation_4()
    test_conversation_5()

    print(f"\n{'=' * 50}")
    print(f"{_passed} passed, {_failed} failed")
    print("=" * 50)
    if _failed:
        print(
            "\nA failure here doesn't automatically mean the code is wrong -- "
            "these are LLM decisions, not deterministic unit tests. Re-run "
            "once; if it fails the same way consistently, check the numbered "
            "rule in agent.py's SYSTEM prompt that the failing check maps to."
        )
