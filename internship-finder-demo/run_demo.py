"""
Runs the same 5-turn conversation (explained in README.md) against BOTH
agents back to back, so you can see the contrast without manually
retyping the script into two separate terminal sessions.

Run:  python run_demo.py
"""

import tools               # for tools.reset_status()
import stateless_agent     # for stateless_agent.run_agent()
import multi_turn_agent    # for multi_turn_agent.run_agent()

# The canned conversation. Each string is one user turn, fed to both
# agents in the same order. See README.md for why each line is there.
SCRIPT = [
    "I'm looking for a software engineering internship, ideally remote and paid.",
    "Also show me some ML internship options, I'm open to onsite for those.",
    "I don't want unpaid roles at all, and I really want a company with strong "
    "mentorship -- cross off anything without that noted.",
    "Wait, I already interned at a BrightPath-adjacent startup last summer "
    "through a friend's referral, so I'd rather apply somewhere new. Also, "
    "track the Nimbus one as 'applied' since I just submitted my application there.",
    "Given everything so far, what's my shortlist? And which one should I "
    "prioritize applying to first given deadlines?",
]


def run_stateless() -> None:
    print("\n" + "=" * 70)  # visual separator so the two sections are easy to tell apart in the terminal
    print("STATELESS AGENT -- messages rebuilt fresh on every turn")
    print("=" * 70)
    tools.reset_status()   # clean slate -- otherwise the multi-turn run below would see leftover state
    for i, turn in enumerate(SCRIPT, start=1):   # i counts from 1, turn is the actual message text
        print(f"\n--- Turn {i} ---")
        print(f"> {turn}")
        # No shared `messages` variable passed in here -- each call is
        # completely independent, exactly the bug this whole demo is about.
        print(stateless_agent.run_agent(turn))   # each call gets ONLY this one string, nothing else


def run_multi_turn() -> None:
    print("\n" + "=" * 70)  # same visual separator, labeling the second section
    print("MULTI-TURN AGENT -- messages persist across every turn")
    print("=" * 70)
    tools.reset_status()   # clean slate, independent of the stateless run above
    messages: list[dict] = []   # created once, BEFORE the loop -- passed into every call below
    for i, turn in enumerate(SCRIPT, start=1):   # same script, same order, as the stateless run
        print(f"\n--- Turn {i} ---")
        print(f"> {turn}")
        print(multi_turn_agent.run_agent(messages, turn))   # `messages` accumulates across every iteration


if __name__ == "__main__":  # only runs when this file is executed directly
    run_stateless()    # section 1: watch it fail
    run_multi_turn()   # section 2: watch it succeed on the exact same script
    print("\n" + "=" * 70)
    print("Compare Turn 5 in each section above -- that's the payoff turn.")
    print("=" * 70)
