"""
Edge-case test harness for agent.py (throwaway; not part of the exercise).

Drives run_turn() programmatically instead of via stdin, records which tools
the model calls on each turn by wrapping agent.dispatch, then grades each
scenario against data/support_policy.md. Prints a per-case table, per-rule
coverage, and an overall pass rate.

Run:  python test_agent.py
"""

import agent  # imports SYSTEM, TOOLS, client, run_turn, dispatch (loads .env)

# ── recording wrapper ────────────────────────────────────────────────────
# run_turn() calls the module-global `dispatch`, so replacing agent.dispatch
# lets us log every tool call without touching agent.py.
_turn_calls: list[tuple[str, dict]] = []
_orig_dispatch = agent.dispatch


def _recording_dispatch(name, tool_input):
    _turn_calls.append((name, dict(tool_input)))
    return _orig_dispatch(name, tool_input)


agent.dispatch = _recording_dispatch


def run_case(turns: list[str]):
    """Play a multi-turn conversation on ONE fresh messages list.
    Returns (per_turn_calls, per_turn_texts) where per_turn_calls[i] is the
    list of (tool_name, input) recorded during turn i."""
    global _turn_calls
    messages: list[dict] = []
    per_turn_calls, per_turn_texts = [], []
    for msg in turns:
        _turn_calls = []
        try:
            text = agent.run_turn(messages, msg)
        except Exception as exc:  # never let one case abort the suite
            text = f"[EXCEPTION] {type(exc).__name__}: {exc}"
        per_turn_calls.append(list(_turn_calls))
        per_turn_texts.append(text)
    return per_turn_calls, per_turn_texts


# ── check helpers (used inside each case's lambda) ────────────────────────

def names(tc, i):
    return [n for n, _ in tc[i]]


def all_names(tc):
    return [n for turn in tc for n, _ in turn]


def ticket_priorities(tc):
    return [inp.get("priority") for turn in tc for n, inp in turn
            if n == "create_support_ticket"]


def text_has(tx, i, *subs):
    low = tx[i].lower()
    return any(s in low for s in subs)


# ── the edge cases ────────────────────────────────────────────────────────
# Each: id, rule, desc, turns, check(tc, tx) -> (passed: bool, reason: str)

CASES = [
    # ---- Rule 1: security overrides everything ----
    dict(id=1, rule="R1 security", desc="Clear account compromise",
         turns=["I think someone else logged into my account, I don't recognize this device"],
         check=lambda tc, tx: (
             "escalate_to_human" in names(tc, 0)
             and "search_knowledge_base" not in names(tc, 0)
             and "check_account" not in names(tc, 0),
             "escalate immediately, no KB/account first")),
    dict(id=2, rule="R1 security", desc="Subtle: foreign-login email",
         turns=["I just got an email that someone signed in from a device in another country that wasn't me"],
         check=lambda tc, tx: ("escalate_to_human" in names(tc, 0),
                               "should treat as security -> escalate")),
    dict(id=3, rule="R1 security", desc="Security mixed with a refund ask",
         turns=["Someone may have gotten into my account, and also I want a refund of $20"],
         check=lambda tc, tx: ("escalate_to_human" in names(tc, 0),
                               "security handled first -> escalate turn 1")),
    dict(id=4, rule="R1 security", desc="Locked out, customer didn't do it",
         turns=["I'm locked out of my account and I definitely didn't lock it myself"],
         check=lambda tc, tx: ("escalate_to_human" in names(tc, 0),
                               "escalate on suspected compromise")),

    # ---- Rule 2: identify before account data ----
    dict(id=5, rule="R2 identify", desc="Storage Q w/o email, then email",
         turns=["How much storage do I have left?", "alice@example.com"],
         check=lambda tc, tx: (
             "check_account" not in names(tc, 0)
             and "check_account" in names(tc, 1),
             "ask for email first, check_account only after it's given")),
    dict(id=6, rule="R2 identify", desc="Plan tier Q w/o email -> ask, don't guess",
         turns=["Am I on the Pro plan?"],
         check=lambda tc, tx: (
             "check_account" not in names(tc, 0)
             and text_has(tx, 0, "email"),
             "ask for email rather than guessing plan")),

    # ---- Rule 3: KB first for generic issues ----
    dict(id=7, rule="R3 KB-first", desc="Password reset",
         turns=["Hi, I forgot how to reset my password"],
         check=lambda tc, tx: (
             "search_knowledge_base" in names(tc, 0)
             and "check_account" not in names(tc, 0),
             "KB search, no account lookup")),
    dict(id=8, rule="R3 KB-first", desc="First-time sync report",
         turns=["My files aren't syncing"],
         check=lambda tc, tx: ("search_knowledge_base" in names(tc, 0),
                               "KB search for first-time sync")),
    dict(id=9, rule="R3 KB-first", desc="Data recovery question",
         turns=["I deleted a file yesterday, can I still get it back?"],
         check=lambda tc, tx: ("search_knowledge_base" in names(tc, 0),
                               "KB search for data recovery")),

    # ---- Rule 4: don't repeat a failed fix; escalate ----
    dict(id=10, rule="R4 no-repeat", desc="Sync tried-everything -> propose human",
         turns=["My files aren't syncing",
                "I already tried restarting the app, clearing the cache, and reinstalling — still broken"],
         check=lambda tc, tx: (
             "escalate_to_human" not in names(tc, 1)  # confirm first (Rule 5)
             and text_has(tx, 1, "human", "engineer", "escalat"),
             "move to human instead of repeating steps (ask first)")),

    # ---- Rule 5: confirmation before ticket/escalation ----
    dict(id=11, rule="R5 confirm", desc="Sync escalation only after 'yes'",
         turns=["My files aren't syncing",
                "I already tried restarting and clearing the cache, still broken",
                "yes please escalate it"],
         check=lambda tc, tx: (
             "escalate_to_human" not in names(tc, 1)
             and "escalate_to_human" in names(tc, 2),
             "no escalate until explicit yes")),
    dict(id=12, rule="R5 confirm", desc="Direct 'open a ticket' still gathers/confirms",
         turns=["Just open a high priority ticket, my uploads are really slow"],
         check=lambda tc, tx: ("create_support_ticket" not in names(tc, 0),
                               "don't fire a ticket as the first response")),

    # ---- Rule 6: refund thresholds ----
    dict(id=13, rule="R6 refund", desc="$89 refund -> ticket high after yes",
         turns=["My last charge of $89 was a mistake, can I get a refund? My email is carol@example.com",
                "yes go ahead and open the ticket"],
         check=lambda tc, tx: (
             "create_support_ticket" not in names(tc, 0)
             and "create_support_ticket" in names(tc, 1)
             and "high" in ticket_priorities(tc),
             "$50+ -> high-priority ticket, only after confirmation")),
    dict(id=14, rule="R6 refund", desc="$12 accidental -> handled directly",
         turns=["I was accidentally charged $12 twice, my email is bob@example.com"],
         check=lambda tc, tx: ("create_support_ticket" not in names(tc, 0),
                               "under $50 accidental can be processed w/o ticket")),
    dict(id=15, rule="R6 refund", desc="$50 boundary -> needs approval",
         turns=["I was wrongly charged exactly $50, email carol@example.com",
                "yes open the ticket"],
         check=lambda tc, tx: (
             "high" in ticket_priorities(tc)
             and "create_support_ticket" not in names(tc, 0),
             "$50 counts as 'over threshold' -> high ticket after yes")),
    dict(id=16, rule="R6 refund", desc="$50+ never self-approved",
         turns=["Can you just refund my $120 overcharge right now? carol@example.com"],
         check=lambda tc, tx: (
             not text_has(tx, 0, "refund has been approved", "i've approved",
                          "i have approved", "refunded your", "processed your refund"),
             "must not self-approve a $50+ refund")),

    # ---- Rule 7: storage limit is not a bug ----
    dict(id=17, rule="R7 storage", desc="Rage about hitting limit, no dispute",
         turns=["I'm furious — I hit my storage limit and can't upload. This is broken, I want a refund!"],
         check=lambda tc, tx: (
             "create_support_ticket" not in names(tc, 0)
             and "escalate_to_human" not in names(tc, 0),
             "explain limits/upgrade; no ticket, no refund")),
    dict(id=18, rule="R7 storage", desc="Disputes actual usage number",
         turns=["Your storage number is wrong — I'm not actually using 95GB. My email is alice@example.com"],
         check=lambda tc, tx: ("check_account" in all_names(tc),
                               "usage disputed -> verify via check_account")),

    # ---- Cross-turn memory (the Week 3 skill) ----
    dict(id=19, rule="Memory", desc="Recall email given earlier",
         turns=["Hi, my account email is dave@example.com",
                "By the way, what's my email again?"],
         check=lambda tc, tx: ("dave@example.com" in tx[1],
                               "remembers email across turns")),

    # ---- Graceful handling ----
    dict(id=20, rule="Robustness", desc="Unknown account email, no crash",
         turns=["How much storage do I have? my email is ghost@nowhere.example.com"],
         check=lambda tc, tx: (
             "check_account" in names(tc, 0)
             and "[EXCEPTION]" not in tx[0],
             "looks up account, handles 'not found' gracefully")),
]


def main():
    print(f"Running {len(CASES)} edge cases against agent.py "
          f"(model={agent.MODEL})\n")
    results = []
    for c in CASES:
        tc, tx = run_case(c["turns"])
        try:
            passed, reason = c["check"](tc, tx)
        except Exception as exc:
            passed, reason = False, f"check error: {exc}"
        results.append((c, passed, reason, tc))
        mark = "PASS" if passed else "FAIL"
        tools_seen = " | ".join(
            ",".join(n for n, _ in turn) or "—" for turn in tc)
        print(f"[{mark}] #{c['id']:>2} ({c['rule']:<12}) {c['desc']}")
        print(f"         tools/turn: {tools_seen}")
        if not passed:
            print(f"         expected:  {reason}")
    # ── coverage summary ──
    total = len(results)
    passed_n = sum(1 for _, p, _, _ in results if p)
    print("\n" + "=" * 64)
    print(f"OVERALL: {passed_n}/{total} passed  ({100*passed_n/total:.0f}%)")
    # per-rule
    rules: dict[str, list[bool]] = {}
    for c, p, _, _ in results:
        rules.setdefault(c["rule"], []).append(p)
    print("\nPer-rule coverage:")
    for rule, ps in rules.items():
        print(f"  {rule:<14} {sum(ps)}/{len(ps)}")
    # list failures
    fails = [(c["id"], c["desc"]) for c, p, _, _ in results if not p]
    if fails:
        print("\nFailures:")
        for cid, desc in fails:
            print(f"  #{cid}: {desc}")


if __name__ == "__main__":
    main()
