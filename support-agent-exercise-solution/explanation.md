# Support Concierge Agent — Solution & Explanation

This is the completed version of `../support-agent-exercise/`, plus an
automated test runner. The exercise directory is untouched — this is a
separate, fully-solved reference you can compare your own attempt
against, or just run directly.

## Setup

```bash
cd week-03/support-agent-exercise-solution
pip install -r requirements.txt
cp .env.example .env
```

Add your key to `.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
```

## Running it

**Interactively:**
```bash
python agent.py
```
Same `> ` REPL as every other agent in this project.

**Automated checks:**
```bash
python run_tests.py
```
Runs the exercise's 5 example conversations end to end and prints
PASS/FAIL for each expected decision from `ANSWER_KEY.md` — see "How the
tests work" below.

## What was solved, stage by stage

The exercise's `agent.py` had three TODOs. Here's what each one became
and why.

### Stage 1 — the system prompt

`data/support_policy.md` has 7 numbered rules. The model never reads
that file — nothing in the code sends its contents anywhere. So `SYSTEM`
in `agent.py` restates every rule directly, wrapped in `<policy>` tags,
with `<role>` and `<tools>` sections above it (the same
role → context → rules structure `persona_agent.py` used back in the
main lesson). If a rule isn't in this string, it does not exist as far
as the model is concerned — that's the whole point of the exercise:
`create_support_ticket`'s own tool description already hints at
"only after confirmation," but that instruction has to actually be
enforced somewhere the model reads on every request, which is the
system prompt, not a docstring only a human sees.

### Stage 2 — the per-turn tool loop

`run_turn()` is the same shape used everywhere else in this project
(`reference-agent/stage3_multi_turn_with_tools.py`,
`internship-finder-demo/multi_turn_agent.py`,
`live-internship-search-agent/agent.py`): call the model, append its
response to history immediately, check `stop_reason`, dispatch any
`tool_use` blocks, send all results back as one message, loop. Nothing
support-agent-specific here — this is the generic pattern, just
retargeted at this exercise's four tools.

### Stage 3 — cross-turn memory

`messages: list[dict] = []` is created once, right before the `while
True:` loop starts in `__main__`, and passed into every `run_turn()`
call after that. This is the single line that makes the whole exercise
work: Rule 4 ("don't repeat a step already tried") is only followable
if the agent can see, in the current request, that it already suggested
that step — which requires the earlier turn to still be in `messages`.

## How the tests work

`run_tests.py` doesn't read text and guess — it monkey-patches
`tools.dispatch` to record every `(tool_name, tool_input)` call while
still executing it for real, then runs the exercise's 5 conversations
and asserts on what got called, in what order, with what arguments.

| Conversation | What's asserted | Policy rule it verifies |
|---|---|---|
| 1. Password reset | Turn 1 calls `search_knowledge_base`, not a ticket/escalation. Turn 2 calls nothing. | Rule 3 (KB before account data); no unnecessary tool use |
| 2. Sync issue → escalation | Turn 1 searches the KB. Turn 2 does NOT escalate yet. Turn 3 escalates only after "yes." | Rule 4 (don't repeat a failed fix) + Rule 5 (confirm first) — **the core memory test** |
| 3. Security | Escalates immediately, with no KB search or account check first. | Rule 1 (security skips everything, including confirmation) |
| 4. $89 refund | Turn 1 does NOT create a ticket. Turn 2 creates one, `priority == "high"`, only after "yes." | Rule 5 (confirm first) + Rule 6 (refund threshold) |
| 5. Ask before guessing | Turn 1 does NOT call `check_account` (no email yet). Turn 2 calls it with the right email. | Rule 2 (identify the customer first) |

## A note on the tests being non-deterministic

These are behavioral checks against a live model, not unit tests against
pure functions — the same conversation can occasionally produce a
slightly different tool-call sequence between runs, especially on
borderline phrasing. A single failure isn't proof of a bug. If a
specific check fails **consistently** across multiple runs, that's a
real signal: go to the rule number in the table above, find it in
`agent.py`'s `SYSTEM` string, and sharpen the wording — this is the same
prompt-iteration loop you'd use writing your own version.

## Comparing against your own attempt

If you wrote your own `agent.py` in `../support-agent-exercise/`, the
fastest way to compare is to copy `run_tests.py` and `tools.py`'s
`_TICKETS` reset pattern over — point the `import agent` line at your
version instead, and run it. Passing all 5 conversations here is a
stronger signal than eyeballing `ANSWER_KEY.md` by hand.
