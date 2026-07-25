# Demo — Multi-Turn vs. Stateless: Finding Internships

A worked demonstration (not an exercise -- everything here is complete
and runnable) showing exactly what multi-turn memory buys you, using a
concrete, valuable task: an agent that helps find and narrow down
internship applications over a realistic back-and-forth conversation.

## Setup

**Prerequisites:** Python 3.10+, and an Anthropic API key (console.anthropic.com if you don't have one).

```bash
cd week-03/internship-finder-demo
pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and paste in your key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

That's it -- no other config, no database, no external services.

## Running the demo

**The main event — automated side-by-side comparison:**

```bash
python run_demo.py
```

Runs the same 5-turn script (below) against both agents back to back and
prints both full transcripts to your terminal. This is the fastest way
to see the contrast -- no typing required. Takes well under a minute;
costs a few cents in API usage (10 short calls total).

**Interactive mode — talk to one agent at a time:**

```bash
python multi_turn_agent.py    # remembers everything across turns
```
```bash
python stateless_agent.py     # forgets everything between turns
```

Both drop you into a `> ` prompt. Type a message, hit Enter, read the
reply, repeat. `Ctrl+C` to quit. Use these to go off-script and test the
difference yourself with your own conversation -- see "Try it yourself"
at the bottom.

**If something goes wrong:**
- `AuthenticationError` / 401 → check `.env` actually has your real key on the `ANTHROPIC_API_KEY=` line, no quotes, no extra spaces.
- `ModuleNotFoundError: No module named 'anthropic'` → you're not in this directory, or `pip install -r requirements.txt` targeted a different Python than the one running the script (check `which python3` / your virtualenv is active).
- `FileNotFoundError` for `internships.json` → run the scripts from *inside* `internship-finder-demo/`, not from `week-03/` — the data path is relative to the script's own directory via `BASE_DIR`, so this should already work regardless of your current shell directory, but confirm you didn't move `tools.py` away from `data/`.

## How the code is structured

Two agents, `stateless_agent.py` and `multi_turn_agent.py`, are
identical except for ONE thing: whether the `messages` list persists
across calls to `run_agent()`. Same tools (`search_internships`,
`get_internship_details`, `track_status`, `list_tracked`), same system
prompt word for word, same model. This isolates the variable completely
-- any difference in behavior you see comes from that one line, not
from a smarter prompt or better tools.

## Data

`data/internships.json` -- 12 synthetic listings spanning software
engineering, ML, data science, finance, and marketing; paid and unpaid;
remote and onsite; with and without a noted mentorship program. Two
listings (INT-001 and INT-012) are deliberately from the same company
under different teams, to test whether an agent picks up "I don't want
that company again" as a *company-level* exclusion, not just avoiding
the one listing ID it happened to mention.

## The script, and why each turn matters

1. *"I'm looking for a software engineering internship, ideally remote
   and paid."* -- establishes the first constraint (remote + paid + SWE).
2. *"Also show me some ML internship options, I'm open to onsite for
   those."* -- adds a SECOND, independent constraint set. Working memory
   has to hold both simultaneously: don't drop the SWE preference just
   because we're now talking about ML.
3. *"I don't want unpaid roles at all, and I really want a company with
   strong mentorship -- cross off anything without that noted."* --
   retroactively narrows BOTH earlier categories with a new global
   filter. This only works if the agent remembers what it already
   showed you in turns 1 and 2 -- there's nothing to "cross off" without
   that history.
4. *"Wait, I already interned at a BrightPath-adjacent startup... I'd
   rather apply somewhere new. Also track the Nimbus one as 'applied'."*
   -- a preference stated in plain language with no corresponding tool
   filter (there's no `exclude_company` parameter) -- the agent has to
   reason over conversation history to apply it. "The Nimbus one" is
   also a bare reference that only resolves if turn 1's search results
   are still in context.
5. *"Given everything so far, what's my shortlist? And which one should
   I prioritize applying to first given deadlines?"* -- the payoff turn.
   Answering this well requires synthesizing all four prior turns at
   once. No single tool call produces this answer -- it has to come
   from reasoning over accumulated context.

## What to expect

**Stateless agent:** turns 1-2 look fine in isolation (each is a
self-contained request it can actually search for). By turn 3, "cross
off anything" has nothing to reference -- it may re-search from
scratch, ask you to restate your preferences, or apply the new filter
to an unrelated fresh search. Turn 4's "the Nimbus one" and the
BrightPath exclusion are meaningless to it -- it has no idea what was
found in turn 1. Turn 5 is where it fully breaks: it has no "everything
so far" to summarize, because each turn was answered in total
isolation. Watch for it saying something like "I don't have information
about a prior shortlist" or fabricating one from nothing.

**Multi-turn agent:** turn 3 should visibly narrow the running set from
turns 1-2 against the new paid+mentorship filter. Turn 4 should exclude
BOTH BrightPath listings (INT-001 and INT-012) going forward, and
correctly resolve "the Nimbus one" to INT-005 without being told the
ID. Turn 5 should produce a real synthesized shortlist and a
deadline-based recommendation, built from everything actually
discussed -- not a generic re-search.

## The actual lesson

Better tools and a better system prompt cannot fix what turn 5 needs.
The stateless agent's system prompt EXPLICITLY says "factor all
preferences into your recommendations, not just the most recent
message" -- and it still can't, because those earlier preferences
simply are not present in the request. Multi-turn looping isn't an
enhancement to a good agent; for any task involving more than one
exchange, it's a precondition for the agent being able to do the task
at all. This is the same conclusion `../reference-agent/` demonstrated
in the abstract, now shown mattering on a task with a real, gradable
outcome: does the final shortlist actually reflect what the candidate said?

## Try it yourself

Run `python multi_turn_agent.py` and go off-script -- state a
preference, contradict yourself two turns later, ask it to justify a
recommendation using something you said five turns ago. Then run the
same thing against `python stateless_agent.py` and watch it fail in
real time.
