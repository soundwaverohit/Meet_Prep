#!/usr/bin/env python3
"""
Additional edge cases to reach 100% coverage.
These test scenarios not covered in the initial 20 tests.
"""

from agent import run_turn

ADDITIONAL_TESTS = []

class TestCase:
    def __init__(self, name, turns, expected_behaviors):
        self.name = name
        self.turns = turns
        self.expected_behaviors = expected_behaviors

    def run(self):
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

# Additional edge case tests

ADDITIONAL_TESTS.append(TestCase(
    "21. Plain Acknowledgment - No tool call",
    [
        ("Hi, I forgot how to reset my password", "Ask password question"),
        ("Thanks, that worked!", "Plain thanks acknowledgment"),
    ],
    [
        (1, "Should search KB",
         lambda r: "reset" in r.lower()),
        (2, "Should NOT call any tool for plain thanks, just acknowledge",
         lambda r: len(r.split()) < 30 and "tool" not in r.lower()),
    ]
))

ADDITIONAL_TESTS.append(TestCase(
    "22. Explicit Escalation Confirmation - Sync after failed steps",
    [
        ("Files aren't syncing", "Report sync"),
        ("I tried restarting", "One step tried"),
        ("Still broken", "Confirm failure"),
        ("Please escalate", "Ask for escalation"),
    ],
    [
        (3, "Should explicitly propose escalation and ask confirmation",
         lambda r: ("escalat" in r.lower() and ("would you" in r.lower() or "like" in r.lower() or "want" in r.lower() or "confirm" in r.lower()))),
        (4, "Should escalate after customer confirms",
         lambda r: "ticket" in r.lower() or "escalat" in r.lower()),
    ]
))

ADDITIONAL_TESTS.append(TestCase(
    "23. Vague Refund Request - No amount specified",
    [
        ("I need a refund", "Vague refund request without amount"),
    ],
    [
        (1, "Should ask for details about the charge amount",
         lambda r: "amount" in r.lower() or "charge" in r.lower() or "how much" in r.lower()),
    ]
))

ADDITIONAL_TESTS.append(TestCase(
    "24. $50.01 Refund - Just over threshold",
    [
        ("I was charged $50.01 by mistake. Email: bob@example.com", "Request $50.01 refund"),
        ("yes, open ticket", "Confirm"),
    ],
    [
        (1, "Should require ticket for $50.01",
         lambda r: "ticket" in r.lower() and "billing" in r.lower()),
        (2, "Should open high priority ticket",
         lambda r: "ticket" in r.lower() and "high" in r.lower()),
    ]
))

ADDITIONAL_TESTS.append(TestCase(
    "25. Billing + KB First - Payment issue mentioned",
    [
        ("My payment failed. What do I do?", "Ask about failed payment"),
    ],
    [
        (1, "Should search KB for billing info",
         lambda r: ("retry" in r.lower() or "automatic" in r.lower())),
    ]
))

ADDITIONAL_TESTS.append(TestCase(
    "26. Vague Security Mention - Should escalate anyway",
    [
        ("I think my password might have been seen", "Vague but security-related"),
    ],
    [
        (1, "Should escalate for potential security issue",
         lambda r: "escalat" in r.lower()),
    ]
))

ADDITIONAL_TESTS.append(TestCase(
    "27. Follow-up After Resolution",
    [
        ("How do I reset password?", "First question"),
        ("That worked!", "Solved"),
        ("What about two-factor auth?", "New related question"),
    ],
    [
        (1, "Should answer from KB",
         lambda r: "reset" in r.lower()),
        (3, "Should search KB for 2FA, not re-ask for email",
         lambda r: "2fa" in r.lower() or "two" in r.lower() or "factor" in r.lower() or "authentication" in r.lower()),
    ]
))

ADDITIONAL_TESTS.append(TestCase(
    "28. Account Check After Email Provided",
    [
        ("What's my plan?", "Ask account question without email"),
        ("alice@example.com", "Provide email"),
    ],
    [
        (1, "Should ask for email",
         lambda r: "email" in r.lower()),
        (2, "Should check account and return plan info",
         lambda r: "pro" in r.lower() or "plan" in r.lower()),
    ]
))

ADDITIONAL_TESTS.append(TestCase(
    "29. Refund Request With Email - Process directly if under $50",
    [
        ("I was overcharged $25 for a duplicate. Email: bob@example.com", "Request $25 refund with email"),
    ],
    [
        (1, "Should process directly without ticket for $25",
         lambda r: "process" in r.lower() or "refund" in r.lower() or "credit" in r.lower()),
    ]
))

ADDITIONAL_TESTS.append(TestCase(
    "30. Escalation Confirmation Explicit - Not just proposing",
    [
        ("My sync is broken and I've tried everything", "Multiple failed attempts"),
        ("Can you escalate?", "Direct request to escalate"),
    ],
    [
        (2, "Should ask 'Do you want me to escalate?' or similar confirmation",
         lambda r: "escalat" in r.lower() and ("confirm" in r.lower() or "would you" in r.lower() or "want" in r.lower() or "?" in r)),
    ]
))

def main():
    print("\n" + "="*70)
    print("ADDITIONAL EDGE CASE TESTS (21-30)")
    print("="*70)

    results = {"pass": 0, "partial": 0, "fail": 0}

    for test in ADDITIONAL_TESTS:
        result = test.run()
        results[result] += 1

    print(f"\n\n{'='*70}")
    print("ADDITIONAL TESTS SUMMARY")
    print(f"{'='*70}")
    print(f"Total:    {len(ADDITIONAL_TESTS)}")
    print(f"✓ PASS:   {results['pass']}")
    print(f"⚠ PARTIAL: {results['partial']}")
    print(f"✗ FAIL:   {results['fail']}")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
