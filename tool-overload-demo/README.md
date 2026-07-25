# Demo — Tool Overload vs. Orchestration

Why giving one agent too many tools and too much merged context can hurt
its performance, and why an orchestrator that routes to focused
specialists doesn't have that problem — demonstrated with two agents
built from the exact same tools, same data, same model.

## Setup

```bash
cd week-03/tool-overload-demo
pip install -r requirements.txt
cp .env.example .env
```

Add your key to `.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
```

## Running it

```bash
python compare.py
```

Runs 6 test prompts against both agents back to back and prints
PASS/FAIL per prompt plus a token total for each system.

You can also talk to either one directly:
```bash
python kitchen_sink_agent.py
python orchestrator_agent.py
```
Both print which tool(s) fired and the token cost after every reply.

## The two architectures

**`kitchen_sink_agent.py`** — one agent, all 7 tools from three
unrelated domains (Nimbus support, internship search, arithmetic),
declared at once. One system prompt tries to hold all three domains'
policies simultaneously. Every single request sends all 7 tool schemas
and the entire merged prompt, whether the question needs one of them or
none of them.

**`orchestrator_agent.py`** — a router with exactly 3 tools, none of
which are the real domain tools. Each is a "delegate" — `delegate_to_support`,
`delegate_to_internship`, `delegate_to_calculator` — that internally
runs a completely separate, focused sub-agent scoped to only that
domain's tools (1-4 of them) and only that domain's policy. The
orchestrator's own request never includes support, internship, or
calculator tool schemas at all; those only get sent on the *second*,
inner API call, made by whichever specialist got picked.

Same underlying `tools.py` powers both — same `search_knowledge_base`,
same `escalate_to_human`, same `calculator`. The only thing that differs
is how much of it any single API call has to hold at once.

## Why this matters: two separate failure modes

**1. Tool selection gets harder as the list grows.** With 7 tools mixing
three unrelated domains, some genuinely share vocabulary —
`search_knowledge_base` and `search_internships` both start with
"search"; `check_account` and `track_status` are both "look something
up by ID" shaped. The model has to disambiguate between all 7 on every
single request, even for a trivial arithmetic question. At 7 tools a
strong model usually gets this right most of the time — but this
doesn't scale. Real agents accumulate far more than 7 tools as
capabilities get bolted on over months, and tool-selection accuracy
degrades as the list grows, especially for tools with overlapping
descriptions.

**2. Merged policy prompts dilute specific rules.** The kitchen sink's
system prompt has to compress Rule 1 ("security overrides everything,
escalate with NO confirmation") down to one clause inside a paragraph
also covering refunds, knowledge-base lookups, internship search, and
arithmetic. The full, unambiguous version of that rule lives in
`orchestrator_agent.py`'s `SUPPORT_SYSTEM` — undiluted, because it's the
*entire* prompt the support specialist sees, not one clause competing
with two other domains for the model's attention.

**3. Token cost is a guaranteed cost, not a maybe.** Regardless of
whether the kitchen sink gets a given prompt right, it pays for all 7
tool schemas plus the full merged prompt on *every* request — including
"what's 2847 times 39?", which needs exactly one tool. The orchestrator
pays for a tiny 3-tool routing prompt on the outer call, then only the
calculator specialist's single tool schema on the inner call. Run
`compare.py` and look at the token totals: the gap you see is structural,
not incidental, and it gets worse as more tools get added to the kitchen
sink — the orchestrator's per-specialist cost never grows, no matter how
many total domains exist system-wide.

## Reading the compare.py output honestly

Sonnet 5 is a strong model — at only 7 tools, don't be surprised if the
kitchen sink gets most or even all 6 test prompts right most runs. The
accuracy gap is real but is more pronounced as the tool count grows
past what one prompt can cleanly hold (think 20-30 tools across many
real integrations, not 7). What's **guaranteed** on every run, tool
count aside, is the token total: the orchestrator's total should
consistently come in lower per-prompt for anything that only needs one
domain, because it never pays for the other two domains' schemas at
all. That guaranteed efficiency gap, plus the accuracy gap that widens
as more tools get added, is the actual case for orchestration — not "the
kitchen sink is always wrong," but "the kitchen sink pays a real,
compounding cost that the orchestrator structurally avoids."

## Try it yourself

Add a 4th domain to `tools.py` (anything — weather, a calendar, a
translator) and:
- add its tools to `kitchen_sink_agent.py`'s `ALL_TOOLS` and merge its
  policy into the one `SYSTEM` string
- add one more `delegate_to_X` function and schema to
  `orchestrator_agent.py`, with its own small, undiluted system prompt

Re-run `compare.py`. The kitchen sink's per-request token cost goes up
for *every* prompt, even ones unrelated to the new domain. The
orchestrator's cost for existing prompts doesn't move at all.
