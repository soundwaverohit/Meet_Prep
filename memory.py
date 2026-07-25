"""
Memory -- rolling window + summarization for multi-turn conversations.
Keeps recent turns verbatim; once accumulated token usage crosses a
threshold, older turns are folded into a running summary so the
conversation can continue indefinitely without unbounded token growth.
"""

import anthropic

SUMMARY_TRIGGER_TOKENS = 3000   # once cumulative token spend since the last summary exceeds this, summarize
KEEP_RECENT_TURNS = 4           # always keep this many of the most recent turns verbatim, never summarized


class Memory:
    def __init__(self, client: anthropic.Anthropic, model: str):
        self.client = client   # reused for the summarization call in _summarize() -- same client, no new connection
        self.model = model     # which model writes the summary; usually the same one running the conversation
        self.turns: list[dict] = []          # the actual {"role", "content"} messages, same shape as the API expects
        self.summary: str | None = None      # compressed text standing in for everything older than `turns`
        self._tokens_since_summary = 0       # running counter, reset every time _summarize() fires

    def add_turn(self, role: str, content: str) -> None:
        # Appends one message dict onto the running list. Called once per
        # user message and once per assistant reply -- exactly like
        # Stage 2's messages.append(), just wrapped in a method here.
        self.turns.append({"role": role, "content": content})

    def track_usage(self, usage) -> None:
        # `usage` is the .usage object off an API response, carrying
        # input_tokens and output_tokens for that one call. We add both
        # to the running counter, then check whether it's time to
        # compress older history.
        self._tokens_since_summary += usage.input_tokens + usage.output_tokens
        if self._tokens_since_summary > SUMMARY_TRIGGER_TOKENS and len(self.turns) > KEEP_RECENT_TURNS:
            self._summarize()

    def _summarize(self) -> None:
        # Split turns into "everything except the last KEEP_RECENT_TURNS"
        # (to be compressed) and "the last KEEP_RECENT_TURNS" (kept as-is).
        # Negative slicing: turns[:-4] is everything up to the last 4;
        # turns[-4:] is just the last 4.
        older, recent = self.turns[:-KEEP_RECENT_TURNS], self.turns[-KEEP_RECENT_TURNS:]

        # Flatten the older turns into plain "role: content" lines so we
        # can hand them to the model as a normal text prompt.
        transcript = "\n".join(f"{t['role']}: {t['content']}" for t in older)
        prompt = (
            "Summarize the older turns of this conversation into a compact memory "
            "block for a copywriting assistant. Preserve the brief, brand details, "
            "and any decisions made. Be concise -- a few sentences.\n\n" + transcript
        )

        # A SEPARATE, one-off API call whose only job is producing the
        # summary -- this is not part of the main conversation loop, and
        # its own usage isn't fed back into track_usage() (a simplification
        # for this lab; a production system would account for it too).
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=300,   # summaries should be short -- this caps runaway summarization output
            messages=[{"role": "user", "content": prompt}],
        )
        new_summary = next((b.text for b in resp.content if b.type == "text"), "")

        # Append the new summary onto any prior summary rather than
        # replacing it -- so information from several rounds of
        # compression accumulates instead of being lost each time.
        self.summary = f"{self.summary}\n{new_summary}" if self.summary else new_summary

        # The compressed older turns are dropped entirely; only the
        # recent ones (kept verbatim) remain in `self.turns` going
        # forward. This is what actually saves tokens on future calls.
        self.turns = recent
        self._tokens_since_summary = 0   # reset the counter -- we just paid down the "debt"

    def as_messages(self) -> list[dict]:
        # Returns a COPY (list(...)) of the current turns, not the
        # internal list itself -- callers can safely pass this straight
        # to messages.create(messages=...) without risk of it being
        # mutated from outside this class.
        return list(self.turns)

    def summary_block(self) -> str:
        # "" (falsy) when there's no summary yet, so callers can just do
        # `if memory.summary_block():` without a None check.
        return self.summary or ""
