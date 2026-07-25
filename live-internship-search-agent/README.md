# Live Internship Search Agent

A multi-turn agent that finds **real** internships on the live internet
and permanently saves them into `data/internships.json` -- but only when
you explicitly ask it to search. Everything here is complete and
runnable, building directly on `../internship-finder-demo/` (left
untouched) and `../support-agent-exercise/`'s confirmation-gating idea.

## Setup

**Prerequisites:** Python 3.10+, an Anthropic API key.

```bash
cd week-03/live-internship-search-agent
pip install -r requirements.txt
cp .env.example .env
```

Add your key to `.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
```

No other services or API keys needed -- the live web search runs on
Anthropic's own infrastructure, not a separate search API you have to
configure.

## Running it

```bash
python agent.py
```

Drops you into a `> ` prompt. Type a message, hit Enter, read the
reply, repeat. `Ctrl+C` to quit.

## The core design decision: two tiers of "search"

This agent has FOUR tools, split into two tiers:

| Tier | Tool(s) | Cost | When the agent should use it |
|---|---|---|---|
| Local | `search_saved_internships`, `list_saved_internships` | Free, instant | General questions, follow-ups, "show me the remote ones," anything about internships already found |
| Live | `web_search` (Anthropic's built-in tool) + `save_internship` | Real API cost, real internet | **Only** when you explicitly ask it to search |

The system prompt in `agent.py` is the only thing enforcing that
boundary -- nothing in the tool definitions themselves stops the model
from web-searching on every turn. This is the exact same
confirmation-gating pattern as the support-agent-exercise's "don't
create a ticket without asking first," just applied to a more expensive
action (a real network call) instead of a support ticket.

**Try this to see the boundary in action:**
```
> I'm interested in machine learning internships
```
Should use `search_saved_internships` (or say nothing is saved yet if
the file is empty) -- NOT trigger a live search, because "search" was
never said.
```
> Search for real machine learning internships posted this month
```
NOW it should call `web_search`, evaluate the results, and call
`save_internship` for each genuine match -- because you explicitly said
"search."
```
> Show me what you found
```
Back to `search_saved_internships` -- this is a follow-up about
existing results, not a new search request.

## What actually happens when it searches

1. You ask it to search for something specific.
2. Claude calls the built-in `web_search` tool. Anthropic's own servers
   run the search and return results as content blocks in the same
   response -- there's no Python function for this in `tools.py`, and
   we never execute it ourselves (see the comment block in `agent.py`
   above the `TOOLS` list).
3. Claude reads the results and, for each real, current, specific
   listing it finds, calls our custom `save_internship` tool with the
   company, role, location, pay, and a `source_url`.
4. `save_internship` checks for a duplicate (same company+role+location,
   case-insensitive), then appends the new entry to
   `data/internships.json` and rewrites the whole file.
5. Claude summarizes what it found and saved back to you in plain text.

Open `data/internships.json` after a search to see the real entries
that got written -- each one carries `source_url` and `date_added` so
you can trace exactly where it came from and when it was added.

## Why `save_internship` needs a duplicate check

Ask it to search for the same thing twice (or search for two overlapping
queries) and a real search engine will often surface the same posting
again. Without `_is_duplicate()` in `tools.py`, `data/internships.json`
would accumulate the same internship over and over. The check compares
lowercased, stripped `(company, role, location)` -- good enough for a
demo; a production system would need fuzzier matching (e.g. the same
company spelled two different ways).

## A subtlety in the loop: `pause_turn`

`web_search` runs server-side and can itself chain multiple searches in
one turn. If that internal chain hits its own iteration cap before
Claude is done, the response comes back with `stop_reason: "pause_turn"`
instead of a final answer or a `tool_use` request. `agent.py`'s loop
handles this explicitly: it does NOT send a "Continue" message (which
Anthropic's docs warn against) -- it just calls `messages.create()`
again with nothing new appended, because the paused assistant turn
already in `messages` is exactly what the API needs to resume on its
own. This is a real subtlety of the built-in web_search tool that
doesn't come up with fully custom, client-executed tools like the ones
in the other week-03 exercises.

## Design decisions worth knowing about

- **Why a system prompt and not a code-level guardrail?** You could
  imagine hard-blocking `web_search` unless the literal word "search"
  appears in the user's message -- but that's brittle ("look up," "find
  me," "go check" all mean the same thing) and duplicates what the model
  is already good at: understanding intent. This mirrors the
  support-agent-exercise's stretch goal, which asks you to compare a
  prompt-only guardrail against a hard-coded one -- try adding a keyword
  check here yourself and see how it trades off against the prompt-only
  version.
- **Why does `save_internship` compute `date_added` in Python, not ask
  the model for it?** The model has no reliable way to know "today's
  date" unless you tell it, and even then it can drift over a long
  conversation. Anything the code can compute deterministically, the
  code should compute -- never delegate that to the model's guess.
- **Why does `data/internships.json` start empty?** So you can watch it
  go from nothing to real, sourced data in one search -- the whole point
  of this directory is that the dataset is genuinely built by the agent,
  not seeded with fixtures like `../internship-finder-demo/`'s.
