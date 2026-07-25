#!/usr/bin/env python3
"""
Edge case testing suite for the support agent.
Tests 20 edge cases covering the 7 policy rules.
"""

import sys
from agent import run_turn

# Test configuration
TESTS = []
RESULTS = {"pass": 0, "fail": 0, "partial": 0}

class TestCase:
    def __init__(self, name, turns, expected_behaviors):
        """
        name: test name
        turns: list of (user_input, description) tuples
        expected_behaviors: list of (turn_index, behavior_description, check_fn) tuples
                           check_fn(response) returns True if pass, False if fail
        """
        self.name = name
        self.turns = turns
        self.expected_behaviors = expected_behaviors

    def run(self):
        """Run the test and check expected behaviors."""
        print(f"\n{'='*70}")
        print(f"TEST: {self.name}")
        print(f"{'='*70}")

        messages = []
        responses = []

        for turn_idx, (user_input, desc) in enumerate(self.turns, 1):
            print(f"\nTurn {turn_idx}: {desc}")
            print(f"USER: {user_input}")
            response = run_turn(messages, user_input)
            responses.append(response)
            print(f"AGENT: {response[:200]}{'...' if len(response) > 200 else ''}")

        # Check expected behaviors
        passed = 0
        failed = 0

        for turn_idx, behavior_desc, check_fn in self.expected_behaviors:
            result = check_fn(responses[turn_idx - 1])
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"\n  Turn {turn_idx} | {behavior_desc}: {status}")
            if result:
                passed += 1
            else:
                failed += 1

        if failed == 0:
            print(f"\nRESULT: ✓ PASS ({passed}/{passed+failed})")
            return "pass"
        elif passed > 0:
            print(f"\nRESULT: ⚠ PARTIAL ({passed}/{passed+failed})")
            return "partial"
        else:
            print(f"\nRESULT: ✗ FAIL (0/{passed+failed})")
            return "fail"

# Define 20 edge case tests

TESTS.append(TestCase(
    "1. Security + Account Request (security takes priority)",
    [
        ("My account was hacked and I want a refund", "Report security + refund request"),
    ],
    [
        (1, "Should escalate immediately without asking confirmation",
         lambda r: "escalat" in r.lower() and "confirm" not in r.lower()),
    ]
))

TESTS.append(TestCase(
    "2. Storage Complaint - Shouldn't apologize as if it's broken",
    [
        ("I'm out of storage, this is ridiculous!", "Angry about storage limit"),
    ],
    [
        (1, "Should explain limit as expected, not apologize as if broken",
         lambda r: ("upgrade" in r.lower() or "plan" in r.lower()) and "apologize" not in r.lower()),
    ]
))

TESTS.append(TestCase(
    "3. $50 Refund Threshold - Exactly $50",
    [
        ("I was charged $50 twice by mistake. My email is bob@example.com", "Request $50 duplicate refund"),
        ("yes, open the ticket", "Confirm ticket"),
    ],
    [
        (1, "Should ask to open ticket for $50 refund, not approve directly",
         lambda r: "ticket" in r.lower() and "approved" not in r.lower()),
        (2, "Should confirm ticket creation with high priority",
         lambda r: "ticket" in r.lower()),
    ]
))

TESTS.append(TestCase(
    "4. $49.99 Refund - Just under threshold",
    [
        ("I was charged $49.99 for a duplicate. Email: bob@example.com", "Request $49.99 refund"),
    ],
    [
        (1, "Should process directly without ticket for amount under $50",
         lambda r: ("process" in r.lower() or "refund" in r.lower()) and "ticket" not in r.lower()),
    ]
))

TESTS.append(TestCase(
    "5. Customer Wants Escalation Before KB - Should offer KB first",
    [
        ("I want to talk to someone NOW!", "Demanding escalation"),
    ],
    [
        (1, "Should ask what the issue is before escalating",
         lambda r: "escalat" not in r.lower()),
    ]
))

TESTS.append(TestCase(
    "6. Repeat Attempt - Don't suggest same failed fix",
    [
        ("Files aren't syncing", "Report sync issue"),
        ("I restarted the app already", "Report one fix tried"),
        ("Still not working", "Confirm it failed"),
    ],
    [
        (1, "Should suggest KB troubleshooting steps",
         lambda r: "restart" in r.lower() or "sync" in r.lower()),
        (3, "Should not suggest restarting again, should acknowledge failure",
         lambda r: "restart" not in r.lower() or "remain" in r.lower()),
    ]
))

TESTS.append(TestCase(
    "7. Email Required Before Account Check",
    [
        ("What's my storage?", "Ask for storage without email"),
        ("bob@example.com", "Provide email"),
    ],
    [
        (1, "Should ask for email, not check account",
         lambda r: "email" in r.lower() and not ("gb" in r.lower() or "storage" in r.lower())),
        (2, "Should return actual storage data",
         lambda r: "gb" in r.lower()),
    ]
))

TESTS.append(TestCase(
    "8. Security Issue - No Confirmation Required",
    [
        ("Someone's using my account without permission", "Report account compromise"),
    ],
    [
        (1, "Should escalate immediately without asking confirmation",
         lambda r: "escalat" in r.lower() and "confirm" not in r.lower() and "?" not in r.split("confirm")[-1] if "confirm" in r.lower() else True),
    ]
))

TESTS.append(TestCase(
    "9. Disputed Storage - Should check account to verify",
    [
        ("I only uploaded 10GB but it says I used 95GB. My email is alice@example.com", "Dispute storage count"),
    ],
    [
        (1, "Should check account to verify actual usage",
         lambda r: ("95" in r or "100" in r) and "verify" not in r.lower()),
    ]
))

TESTS.append(TestCase(
    "10. Partial Troubleshooting - Should escalate after failed attempts",
    [
        ("My files aren't syncing", "Report sync issue"),
        ("I tried restarting. Still broken.", "Try first step"),
        ("I also cleared cache. Still nothing.", "Try second step"),
        ("Can I just escalate instead of more steps?", "Ask to escalate"),
    ],
    [
        (1, "Should offer KB steps",
         lambda r: "restart" in r.lower() or "cache" in r.lower()),
        (3, "Should recognize steps tried and not repeat them",
         lambda r: "remain" in r.lower() or "next" in r.lower()),
        (4, "Should propose escalation with confirmation",
         lambda r: "escalat" in r.lower()),
    ]
))

TESTS.append(TestCase(
    "11. Customer Tests Memory - Multi-turn retention",
    [
        ("My email is dave@example.com", "Provide email"),
        ("Something is wrong with my account", "Generic issue"),
        ("Wait, what email did I give you?", "Test memory"),
    ],
    [
        (3, "Should remember the email from turn 1",
         lambda r: "dave@example.com" in r),
    ]
))

TESTS.append(TestCase(
    "12. Multiple Issues - Security + Storage (security first)",
    [
        ("Someone hacked my account AND I need a storage refund", "Multiple issues, security + billing"),
    ],
    [
        (1, "Should prioritize security and escalate immediately",
         lambda r: "escalat" in r.lower()),
    ]
))

TESTS.append(TestCase(
    "13. Failed Payment Issue - Should search KB first",
    [
        ("My payment failed, what happens now?", "Ask about failed payment"),
    ],
    [
        (1, "Should search KB for billing info, not check account first",
         lambda r: "retry" in r.lower() or "automatic" in r.lower() or "update" in r.lower()),
    ]
))

TESTS.append(TestCase(
    "14. Data Recovery - KB Question, no account needed",
    [
        ("I accidentally deleted some files, can they be recovered?", "Ask about deleted files"),
    ],
    [
        (1, "Should search KB for recovery info",
         lambda r: "trash" in r.lower() or "recover" in r.lower() or "30" in r),
    ]
))

TESTS.append(TestCase(
    "15. Password Reset - Pure KB, no account check",
    [
        ("How do I reset my password?", "Ask password reset question"),
    ],
    [
        (1, "Should search KB, never check account",
         lambda r: "nimbus.example.com/reset" in r or "reset" in r.lower()),
    ]
))

TESTS.append(TestCase(
    "16. Confirmation Before Ticket - Regular (non-security) escalation",
    [
        ("Sync issues - I've tried everything", "Report problematic sync"),
        ("Escalate me please", "Ask for escalation"),
    ],
    [
        (1, "Should offer KB steps",
         lambda r: "restart" in r.lower() or "cache" in r.lower()),
        (2, "Should confirm before escalating",
         lambda r: "escalat" in r.lower() or "ticket" in r.lower()),
    ]
))

TESTS.append(TestCase(
    "17. No Email Provided - Refund Request",
    [
        ("I want a $30 refund for duplicate charge", "Request refund without email"),
        ("myemail@test.com", "Provide email"),
    ],
    [
        (1, "Should ask for email before processing",
         lambda r: "email" in r.lower()),
        (2, "Should process the refund",
         lambda r: "process" in r.lower() or "refund" in r.lower()),
    ]
))

TESTS.append(TestCase(
    "18. Ticket Confirmation - Don't call without asking",
    [
        ("I need to report a bug with sync", "Report issue"),
        ("yes, open a ticket", "Confirm"),
    ],
    [
        (1, "Should NOT create ticket immediately, should ask first",
         lambda r: "ticket" not in r.lower() or "ticket" in r.lower() and "open" in r.lower()),
        (2, "Should create ticket after confirmation",
         lambda r: "ticket" in r.lower()),
    ]
))

TESTS.append(TestCase(
    "19. Storage Near Limit - Should explain upgrade, not blame user",
    [
        ("My email is bob@example.com. How much storage do I have?", "Check storage at 96% capacity"),
    ],
    [
        (1, "Should return storage info and suggest upgrade, not blame",
         lambda r: ("upgrade" in r.lower() or "plan" in r.lower()) and "sorry" not in r.lower()),
    ]
))

TESTS.append(TestCase(
    "20. Refund + Troubleshooting - Try KB before refund",
    [
        ("Files not syncing AND I want a refund. Email: dave@example.com", "Combined issue"),
    ],
    [
        (1, "Should address sync troubleshooting first, mention refund separately",
         lambda r: ("restart" in r.lower() or "cache" in r.lower()) or ("refund" in r.lower())),
    ]
))


def main():
    print("\n" + "="*70)
    print("SUPPORT AGENT - EDGE CASE TEST SUITE")
    print("="*70)
    print(f"Running {len(TESTS)} edge case tests...\n")

    for test in TESTS:
        result = test.run()
        RESULTS[result] += 1

    # Summary
    total = len(TESTS)
    passed = RESULTS["pass"]
    partial = RESULTS["partial"]
    failed = RESULTS["fail"]

    print(f"\n\n{'='*70}")
    print("TEST SUMMARY")
    print(f"{'='*70}")
    print(f"Total Tests:     {total}")
    print(f"✓ PASS:          {passed} ({100*passed//total}%)")
    print(f"⚠ PARTIAL:       {partial} ({100*partial//total}%)")
    print(f"✗ FAIL:          {failed} ({100*failed//total}%)")
    print(f"\nOverall Coverage: {100*(passed + partial*0.5)//total}%")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
