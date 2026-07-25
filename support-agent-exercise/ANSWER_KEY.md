# Answer Key — spoilers ahead

Don't read this until you've run all five conversations from README.md.
Unlike the loan exercise, there's no single correct sentence to match --
check your agent's *decisions* (which tool it called, when, and whether it
asked first) against what's below, not its exact wording.

---

**1. Password reset**
Turn 1: calls `search_knowledge_base` (query about password/reset), answers
directly from the KB article. No `check_account` call -- this question
never needed account data. No ticket.
Turn 2: no tool call at all -- just acknowledges. If your agent calls a
tool here, the system prompt isn't making it clear that a plain "thanks"
doesn't need a lookup.

**2. Sync issue -> escalation (the core test)**
Turn 1: calls `search_knowledge_base` for sync issues, returns the 4-step
fix (restart, clear cache, reinstall, etc.).
Turn 2: this is the one that actually tests memory. The customer says
they already tried two of those exact steps. The agent must NOT restate
the same steps -- it should recognize (from the conversation history, not
a tool call) that this has already been tried, and propose escalating,
explicitly asking for confirmation first ("Want me to escalate this to an
engineer?" or similar) rather than calling `escalate_to_human` immediately.
If your agent repeats "have you tried restarting the app?" here, Stage 3
(cross-turn memory) isn't wired up correctly, or the system prompt doesn't
encode Rule 4.
Turn 3: only now does `escalate_to_human` get called, with a reason
referencing the sync issue.

**3. Security -> immediate escalation, no confirmation**
Single turn: `escalate_to_human` should be called immediately, with no
prior `search_knowledge_base` or `check_account` call, and no "would you
like me to escalate this?" confirmation step first -- Rule 1 is the one
explicit exception to Rule 5. If your agent asks "should I escalate?"
before doing it, it's treating this like a normal ticket instead of a
security exception.

**4. $89 refund**
Turn 1: since an email is given, `check_account("carol@example.com")` may
or may not be called (the refund amount is what matters, not the account
balance) -- either is reasonable, but the agent must NOT say the refund is
approved. It should explain $50+ refunds need billing-team approval and
ask whether to open a ticket.
Turn 2: only after "yes go ahead" does `create_support_ticket` get called,
with `priority: "high"` and a summary mentioning the $89 charge and that
billing approval is needed.

**5. Ask before guessing**
Turn 1: no `check_account` call. The agent asks for an email -- it has no
way to answer "how much storage do I have left" without knowing whose
account to look up, and Rule 2 says don't guess.
Turn 2: now that the email is given, `check_account("alice@example.com")`
is called, and the answer uses the real numbers (95 GB used of 100 GB
limit, 5 GB remaining) -- not a made-up figure.

---

## Common failure modes to check for

- **Stateless agent**: if turn 2 of conversation 2 doesn't remember turn
  1's suggested fix, `messages` is being rebuilt somewhere instead of
  reused -- re-check Stage 3.
- **Confirmation skipped**: if `create_support_ticket` or
  `escalate_to_human` fires on the very first mention of an issue (outside
  the security case), Rule 5 isn't in the system prompt clearly enough.
- **Guessing instead of asking**: if `check_account` gets called with a
  guessed or empty email, or the agent invents storage numbers instead of
  asking for an email first, Rule 2 needs to be more explicit.
- **Promising a refund**: if the agent tells the customer the $89 refund
  is "processed" without a ticket, Rule 6's threshold isn't encoded.
