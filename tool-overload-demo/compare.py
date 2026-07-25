"""
Head-to-head comparison: the same 6 test prompts, run against
kitchen_sink_agent (all 7 tools + merged prompt, every request) and
orchestrator_agent (routes to focused 1-4-tool specialists). Reports
which underlying tool(s) fired for each prompt, whether that matches
what's expected, and total input tokens spent per system.

Run:  python compare.py
"""

import tools
import kitchen_sink_agent
import orchestrator_agent

TESTS = [
    {
        "label": "Security -> immediate escalation",
        "prompt": "I think someone logged into my account, I don't recognize this device. My email is carol@example.com",
        "expect_called": {"escalate_to_human"},
        "expect_not_called": {"search_knowledge_base", "check_account"},
    },
    {
        "label": "Arithmetic",
        "prompt": "What's 2847 times 39?",
        "expect_called": {"calculator"},
        "expect_not_called": set(),
    },
    {
        "label": "Internship search",
        "prompt": "Tell me about internships in machine learning",
        "expect_called": {"search_internships"},
        "expect_not_called": {"search_knowledge_base"},
    },
    {
        "label": "Internship status check",
        "prompt": "Can you check the status of INT-002?",
        "expect_called": {"track_status"},
        "expect_not_called": {"check_account"},
    },
    {
        "label": "Password reset (KB only)",
        "prompt": "How do I reset my password?",
        "expect_called": {"search_knowledge_base"},
        "expect_not_called": {"check_account"},
    },
    {
        "label": "Refund needs confirmation first",
        "prompt": "My last charge of $89 was a mistake, can I get a refund? My email is dave@example.com",
        "expect_called": set(),
        "expect_not_called": {"create_support_ticket"},
    },
]


def run_system(run_fn, label: str) -> None:
    print(f"\n{'=' * 70}\n{label}\n{'=' * 70}")
    total_tokens = 0
    passed = 0

    for t in TESTS:
        tools.reset_state()   # clean ticket/status state before each prompt, independent of prior prompts
        messages: list[dict] = []
        reply, call_tokens, called = run_fn(messages, t["prompt"])
        called_set = set(called)
        total_tokens += call_tokens

        ok_called = t["expect_called"] <= called_set          # every REQUIRED tool actually fired
        ok_not_called = not (t["expect_not_called"] & called_set)   # none of the FORBIDDEN tools fired
        ok = ok_called and ok_not_called
        passed += int(ok)

        print(f"\n[{'PASS' if ok else 'FAIL'}] {t['label']}")
        print(f"  prompt: {t['prompt']}")
        print(f"  tools called: {called or 'none'}")
        print(f"  tokens: {call_tokens}")
        if not ok:
            print(f"  expected called (at least): {t['expect_called'] or 'none'}")
            print(f"  expected NOT called: {t['expect_not_called'] or 'none'}")

    print(f"\n{label}: {passed}/{len(TESTS)} correct, {total_tokens} total input tokens across all {len(TESTS)} prompts")


if __name__ == "__main__":
    run_system(kitchen_sink_agent.run_agent, "KITCHEN SINK  (7 tools, 3 merged policies, every request)")
    run_system(orchestrator_agent.run_agent, "ORCHESTRATOR  (routes to focused 1-4-tool specialists)")
    print(
        "\nCompare the token totals above directly -- same 6 prompts, same "
        "model, same underlying tools. Any accuracy gap or token gap you "
        "see comes purely from architecture, not from different "
        "capabilities. See README.md for how to read this."
    )
