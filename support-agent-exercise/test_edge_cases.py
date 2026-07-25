"""
Edge-case test harness for agent.py (Support Concierge Agent).

Drives the REAL run_turn() loop against the model, but wraps tools.dispatch
so every tool call the agent makes is recorded. Assertions are made mostly
on tool-call behavior (deterministic, directly reflects policy compliance)
and secondarily on response text (marked "soft").

Run:  ANTHROPIC_API_KEY=<key-or-placeholder> python3 test_edge_cases.py
"""

import os
import sys
import traceback

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-proxy-placeholder")

import agent  # noqa: E402
import tools  # noqa: E402

# ── recording layer ────────────────────────────────────────────────────────
_real_dispatch = tools.dispatch
_calls: list[dict] = []          # every tool call in the current scenario
_turn = {"i": -1}                # which user turn we're on


def _recording_dispatch(name, tool_input):
    _calls.append({"turn": _turn["i"], "name": name, "input": tool_input})
    return _real_dispatch(name, tool_input)


# agent.py did `from tools import dispatch`, so patch the name in agent's namespace
agent.dispatch = _recording_dispatch


def run_scenario(turns):
    """Run a fresh multi-turn conversation; return (calls, responses)."""
    global _calls
    _calls = []
    messages: list[dict] = []
    responses = []
    for i, user_msg in enumerate(turns):
        _turn["i"] = i
        responses.append(agent.run_turn(messages, user_msg))
    return list(_calls), responses


# ── tiny check helpers ───────────────────────────────────────────────────────
def names(calls):
    return [c["name"] for c in calls]


def calls_on(calls, turn):
    return [c for c in calls if c["turn"] == turn]


# ── scenarios ────────────────────────────────────────────────────────────────
# Each scenario: (title, turns, check_fn). check_fn(calls, responses) -> list of
# (ok: bool, soft: bool, description) tuples.

def s_security(calls, responses):
    n = names(calls)
    r0 = responses[0].lower()
    return [
        ("escalate_to_human" in n, False, "escalated to human"),
        ("search_knowledge_base" not in n, False, "did NOT search KB first"),
        ("check_account" not in n, False, "did NOT check account first"),
        (any(c["name"] == "escalate_to_human" and c["turn"] == 0 for c in calls),
         False, "escalated immediately on turn 0 (no confirmation)"),
        (("escalat" in r0 or "security" in r0), True, "response mentions escalation/security (soft)"),
    ]


def s_memory(calls, responses):
    r1 = responses[1].lower()
    return [
        ("bob@example.com" in r1, False, "recalled email 'bob@example.com' from earlier turn"),
    ]


def s_no_repeat_escalate(calls, responses):
    n = names(calls)
    esc_turns = [c["turn"] for c in calls if c["name"] == "escalate_to_human"]
    r1 = responses[1].lower()
    repeated = ("restart" in r1 and "clear" in r1)  # re-suggesting the tried fixes
    return [
        ("search_knowledge_base" in n, False, "searched KB for the sync issue"),
        (len(calls_on(calls, 1)) == 0 or "escalate_to_human" not in names(calls_on(calls, 1)),
         False, "did NOT escalate before confirmation (turn 1)"),
        (2 in esc_turns, False, "escalated only after 'yes' on turn 2"),
        (not repeated, True, "did NOT re-suggest restart+clear-cache on turn 1 (soft)"),
    ]


def s_confirm_declined(calls, responses):
    n = names(calls)
    return [
        ("escalate_to_human" not in n, False, "did NOT escalate — customer declined"),
        ("create_support_ticket" not in n, False, "did NOT open a ticket — customer declined"),
    ]


def s_refund_high(calls, responses):
    tickets = [c for c in calls if c["name"] == "create_support_ticket"]
    r0 = responses[0].lower()
    approved_on_spot = ("refund" in r0 and ("approved" in r0 or "processed" in r0) and "ticket" not in r0)
    return [
        (len(tickets) >= 1, False, "opened a support ticket for the $89 refund"),
        (any(c["turn"] == 1 for c in tickets), False, "ticket opened only after 'yes' (turn 1)"),
        (all(c["input"].get("priority") == "high" for c in tickets) if tickets else False,
         False, "ticket priority = 'high'"),
        (not approved_on_spot, False, "did NOT approve the $50+ refund on the spot (turn 0)"),
    ]


def s_refund_small(calls, responses):
    tickets = [c for c in calls if c["name"] == "create_support_ticket"]
    return [
        (all(c["input"].get("priority") != "high" for c in tickets),
         True, "no high-priority approval ticket for a <$50 accidental charge (soft)"),
    ]


def s_refund_remorse(calls, responses):
    full = " ".join(responses).lower()
    # buyer's remorse: must NOT be processed directly; should go to review/billing
    processed_directly = ("refund" in responses[0].lower() and
                          ("processed" in responses[0].lower() or "refunded you" in responses[0].lower()))
    return [
        (not processed_directly, False, "did NOT process buyer's-remorse refund directly on turn 0"),
        (("review" in full or "billing" in full or "ticket" in full or "team" in full),
         True, "routed to review/billing team (soft)"),
    ]


def s_ask_before_guess(calls, responses):
    n = names(calls)
    r0 = responses[0].lower()
    return [
        ("check_account" not in n, False, "did NOT call check_account without an email"),
        ("email" in r0, False, "asked for the customer's email"),
    ]


def s_unknown_account(calls, responses):
    checked = [c for c in calls if c["name"] == "check_account"]
    r0 = responses[0].lower()
    hinted = any(w in r0 for w in ["double-check", "double check", "no account",
                                   "couldn't find", "could not find", "didn't find",
                                   "did not find", "match", "typo"])
    return [
        (len(checked) >= 1, False, "attempted check_account with the given email"),
        (hinted, False, "told customer no match / asked to double-check the email"),
    ]


def s_storage_limit(calls, responses):
    n = names(calls)
    r0 = responses[0].lower()
    return [
        ("create_support_ticket" not in n, False, "did NOT open a ticket for a storage-limit complaint"),
        ("escalate_to_human" not in n, False, "did NOT escalate a storage-limit complaint"),
        (("upgrade" in r0 or "plan" in r0 or "delete" in r0 or "trash" in r0),
         True, "explained limits / upgrade path (soft)"),
    ]


def s_out_of_scope(calls, responses):
    n = names(calls)
    r0 = responses[0].lower()
    declined = any(w in r0 for w in ["outside", "can't help", "cannot help", "unable",
                                     "not able", "nimbus", "support"])
    return [
        ("create_support_ticket" not in n and "escalate_to_human" not in n,
         False, "did NOT open a ticket / escalate for an off-topic question"),
        (declined, True, "politely declined / said out of scope (soft)"),
    ]


SCENARIOS = [
    ("1. Security bypasses everything (Rule 1)",
     ["I think someone else logged into my account, I don't recognize this device"],
     s_security),
    ("2. Cross-turn memory (core Week 3)",
     ["Hi, my email is bob@example.com", "Remind me — what's my email address?"],
     s_memory),
    ("3. No-repeat + confirmed escalation (Rules 3,4,5)",
     ["My files aren't syncing",
      "I already tried restarting the app and clearing the cache, still broken",
      "yes please escalate it"],
     s_no_repeat_escalate),
    ("4. Confirmation DECLINED — no tool call (Rule 5)",
     ["My files aren't syncing",
      "I tried restart, clearing cache, and reinstalling — still broken",
      "no, don't escalate, I'll just wait"],
     s_confirm_declined),
    ("5. Refund >= $50 -> high-priority ticket (Rule 6)",
     ["My last charge of $89 was a mistake, can I get a refund? My email is carol@example.com",
      "yes go ahead and open the ticket"],
     s_refund_high),
    ("6. Refund < $50 accidental -> handled directly (Rule 6)",
     ["I got double-charged $12 by accident today, can you refund it? email alice@example.com"],
     s_refund_small),
    ("7. Buyer's-remorse refund -> needs review (Rule 6 edge)",
     ["I want a refund on my $30 charge, I just don't use Nimbus anymore. email alice@example.com"],
     s_refund_remorse),
    ("8. Ask for email before account data (Rule 2)",
     ["How much storage do I have left?"],
     s_ask_before_guess),
    ("9. Unknown-account email (Rule 8)",
     ["What's my billing status? My email is nobody@nowhere-xyz.com"],
     s_unknown_account),
    ("10. Storage-limit complaint is not a bug (Rule 7)",
     ["I'm furious — I hit my storage limit and can't upload anything. This is broken!"],
     s_storage_limit),
    ("11. Out-of-scope question (Rule 10)",
     ["What's the weather in Paris today?"],
     s_out_of_scope),
]


# ── runner ───────────────────────────────────────────────────────────────────
def main():
    print("=" * 72)
    print("EDGE-CASE TEST RUN  —  agent.py (Support Concierge)")
    print("=" * 72)

    total_hard = total_hard_pass = 0
    total_soft = total_soft_pass = 0
    scenario_pass = 0
    summary_rows = []

    for title, turns, check in SCENARIOS:
        print(f"\n{'-'*72}\n{title}\n{'-'*72}")
        for t in turns:
            print(f"  > {t}")
        try:
            calls, responses = run_scenario(turns)
        except Exception:
            print("  !! SCENARIO CRASHED:")
            traceback.print_exc()
            summary_rows.append((title, "CRASH"))
            continue

        print("  tool calls: " + (", ".join(
            f"[t{c['turn']}]{c['name']}({c['input']})" for c in calls) or "(none)"))
        print(f"  final reply: {responses[-1][:160].strip()}...")

        checks = check(calls, responses)
        hard_fail = False
        for ok, soft, desc in checks:
            if soft:
                total_soft += 1
                total_soft_pass += 1 if ok else 0
            else:
                total_hard += 1
                total_hard_pass += 1 if ok else 0
                if not ok:
                    hard_fail = True
            tag = ("PASS" if ok else "FAIL") + (" (soft)" if soft else "")
            mark = "✓" if ok else ("~" if soft else "✗")
            print(f"    {mark} [{tag}] {desc}")

        if not hard_fail:
            scenario_pass += 1
        summary_rows.append((title, "PASS" if not hard_fail else "FAIL"))

    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    for title, status in summary_rows:
        print(f"  {status:5}  {title}")
    print("-" * 72)
    print(f"  Scenarios passed (all hard checks): {scenario_pass}/{len(SCENARIOS)}")
    print(f"  Hard checks: {total_hard_pass}/{total_hard} passed")
    print(f"  Soft checks: {total_soft_pass}/{total_soft} passed")
    print("=" * 72)

    # non-zero exit if any hard check failed, for CI use
    sys.exit(0 if total_hard_pass == total_hard else 1)


if __name__ == "__main__":
    main()
