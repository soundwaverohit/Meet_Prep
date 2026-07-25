# Practice Exercise — Support Concierge Agent

This is an independent practice problem, not a walkthrough. `agent.py` is a
skeleton with TODOs; `tools.py` is complete. Your job is to design the
decision loop, not the tools -- see `../persona_agent.py` if you want a
worked example of the memory + system-prompt mechanics first.

## The problem

You work at **Nimbus Cloud Storage**. Build an agent that holds a real
support conversation with a customer -- not a single Q&A, a back-and-forth
where it has to remember what's already been said and decide, turn by
turn, what to do next:

- Search the knowledge base (`data/knowledge_base.md`)?
- Look up the customer's account (`data/accounts.json`)?
- Ask a clarifying question instead of guessing?
- Open a support ticket -- but only after confirming with the customer?
- Escalate straight to a human, skipping everything else?

**The decision rules are intentionally not in the code.** They live in
`data/support_policy.md`. The agent only follows them if you translate
them into the system prompt yourself -- that file is never sent to the API
automatically. This is the same "policy lives in a doc, not the prompt for
free" idea as the loan exercise, but this time the harder part isn't
reading a doc, it's a doc whose rules depend on **what was already said
earlier in the conversation** (Rule 4: don't repeat a fix that already
failed). That requires real multi-turn memory, not just tool-chaining
within one turn.

## Data files

| File | Contents |
|---|---|
| `data/knowledge_base.md` | Six help articles: password reset, sync issues, storage limits, data recovery, billing/failed payments, account security. |
| `data/accounts.json` | 4 synthetic customers keyed by email: plan, storage used/limit, billing status. |
| `data/support_policy.md` | The decision policy: 10 numbered rules covering security escalation, when to ask before looking things up, not repeating failed fixes, confirmation-before-action, refund thresholds, unknown-account handling, ticket priority, and staying in scope. Read it before writing your system prompt. |

All data is synthetic — no real company, no real customers.

## Tools (already built for you)

`tools.py` is complete: `search_knowledge_base`, `check_account`,
`create_support_ticket`, `escalate_to_human`. Read the schemas and
docstrings before you start -- notice `create_support_ticket`'s
description explicitly says "only after confirmation," which is a hint
about where that rule needs to be enforced (the system prompt, since
nothing in the tool itself stops the model from calling it early).

## Build order

1. **System prompt.** Translate `data/support_policy.md` into `SYSTEM` in
   `agent.py`. Don't just say "follow the policy" — Claude doesn't have
   the file. Write out the actual rules.
2. **Per-turn tool loop.** Implement `run_turn()`: call the model, run any
   tool calls, feed results back, repeat until you get a final answer.
   Same shape as Week 2 Stage 4.
3. **Cross-turn memory.** Make the `while True` loop at the bottom own the
   `messages` list and pass it into every call to `run_turn()`. This is
   the part that's actually new this week -- get Stage 2 working as a
   single-turn agent first, then verify state survives across turns.

## Definition of done

- [ ] `agent.py` holds a multi-turn conversation -- test by telling it
      your email in one turn and asking "what's my email?" two turns later.
- [ ] It searches the knowledge base before checking an account for a
      generic question, and asks for an email before checking an account
      for an account-specific one.
- [ ] It does NOT repeat a troubleshooting step the customer already said
      didn't work.
- [ ] It never calls `create_support_ticket` or `escalate_to_human`
      without asking first -- except for a security report, which skips
      straight to escalation with no confirmation.
- [ ] A $89 refund request gets routed to a ticket needing approval, not
      approved on the spot; a refund under $50 for an accidental charge
      can be handled directly.

## Test conversations

Run each of these against your finished agent (multi-turn -- type each
line as a separate input in the same running session):

**1. Knowledge-base only, no account needed**
```
> Hi, I forgot how to reset my password
> Thanks, that worked!
```

**2. Memory + escalation (the core Week 3 test)**
```
> My files aren't syncing
> I already tried restarting the app and clearing the cache, still broken
> yes please escalate it
```

**3. Security skips the queue**
```
> I think someone else logged into my account, I don't recognize this device
```

**4. Refund threshold**
```
> My last charge of $89 was a mistake, can I get a refund? My email is carol@example.com
> yes go ahead and open the ticket
```

**5. Ask before guessing**
```
> How much storage do I have left?
> alice@example.com
```

Check your agent's behavior against `ANSWER_KEY.md` once you've run all
five (kept in a separate file on purpose — don't open it first).

## Stretch goals

- Add the rolling-window summarization from `../memory.py` so long
  conversations don't blow up the context window turn after turn.
- Make `create_support_ticket` reject a call that has no prior customer
  confirmation in the conversation (a hard guardrail in code, not just a
  prompt instruction) -- then see if you can still get the model to
  respect the confirmation rule *without* the code guardrail, and compare
  how reliable prompting alone is.
- Add a `look_up_ticket(ticket_id)` tool so a returning customer can check
  on a previously opened ticket.
