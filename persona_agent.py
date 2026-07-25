"""
Week 3 -- Persona Agent: Marketing Copywriter
Holds a multi-turn conversation as a branded copywriter. Uses memory
(rolling window + summarization, see memory.py) so the agent remembers
the brief across turns, and prints a running token + cost meter.
"""

import anthropic
import yaml
from dotenv import load_dotenv

from memory import Memory   # our own module, defined in memory.py right next to this file

load_dotenv()

client = anthropic.Anthropic()
MODEL = "claude-sonnet-5"

# Sonnet 5 list pricing per million tokens. Used only for the cost
# estimate printed after each turn -- not sent to the API.
INPUT_PRICE_PER_MTOK = 3.00
OUTPUT_PRICE_PER_MTOK = 15.00

# yaml.safe_load() parses brand.yaml into a plain Python dict -- BRAND is
# then just nested dicts/lists, e.g. BRAND["tone_words"] is a list of strings.
with open("brand.yaml") as f:
    BRAND = yaml.safe_load(f)


def build_system_prompt() -> str:
    # Turn the list-shaped YAML fields into comma-separated strings for
    # readable prose inside the prompt.
    tones = ", ".join(BRAND["tone_words"])
    donts = ", ".join(BRAND["donts"])
    # Each example line prefixed with "- " and joined with newlines, so
    # the model sees a bulleted list rather than one run-on sentence.
    examples = "\n".join(f"- {ex}" for ex in BRAND["examples"])

    # The XML-tagged system prompt: <role> establishes identity, <audience>
    # narrows who it's writing for, <voice> encodes tone + hard rules,
    # <format> fixes the output shape, <examples> gives few-shot samples.
    # Separate tags make each section unambiguous to the model, versus one
    # long paragraph where rules can blur together.
    return (
        f"<role>You are the in-house copywriter for {BRAND['name']}.</role>\n"
        f"<audience>{BRAND['audience']}</audience>\n"
        f"<voice>{tones}. Never {donts}.</voice>\n"
        "<format>Return: 3 headline options, 1 body (<=60 words), 1 CTA.</format>\n"
        f"<examples>\n{examples}\n</examples>"
    )


# Built ONCE at import time, not on every turn -- the brand voice doesn't
# change mid-conversation, so there's no reason to rebuild this string
# repeatedly. (The memory summary gets appended to a COPY of this at
# request time, in run_turn() below -- SYSTEM itself stays untouched.)
SYSTEM = build_system_prompt()


class CostMeter:
    def __init__(self):
        self.input_tokens = 0    # running total across the whole session
        self.output_tokens = 0

    def add(self, usage) -> None:
        # Called once per API response; usage is the .usage object off
        # that response (input_tokens/output_tokens for THIS call only).
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens

    def cost(self) -> float:
        # Token counts are per-million-token prices, so divide by
        # 1,000,000 before multiplying by the price to get dollars.
        return (
            self.input_tokens / 1_000_000 * INPUT_PRICE_PER_MTOK
            + self.output_tokens / 1_000_000 * OUTPUT_PRICE_PER_MTOK
        )

    def report(self) -> str:
        total = self.input_tokens + self.output_tokens
        return (
            f"[tokens: {total} ({self.input_tokens} in / {self.output_tokens} out)"
            f" | est. cost: ${self.cost():.4f}]"
        )


def run_turn(memory: Memory, meter: CostMeter, user_msg: str) -> str:
    # Record the human's message in memory FIRST, so it's included in
    # memory.as_messages() below (the API call needs to see it too).
    memory.add_turn("user", user_msg)

    # Start from the static brand prompt, then conditionally graft the
    # memory summary onto a LOCAL COPY -- SYSTEM itself is never mutated,
    # so this doesn't leak between turns or accumulate duplicated text.
    system = SYSTEM
    summary = memory.summary_block()
    if summary:   # empty string is falsy -- this only runs once a summary actually exists
        system += f"\n\n<memory_summary>{summary}</memory_summary>"

    resp = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=system,                 # the (possibly summary-augmented) system prompt for THIS call
        messages=memory.as_messages(), # the recent verbatim turns only -- older history lives in the summary above, not here
    )
    meter.add(resp.usage)          # tally this call's token cost into the running total
    memory.track_usage(resp.usage) # may trigger a summarization pass if we've crossed the threshold

    text = next((b.text for b in resp.content if b.type == "text"), "")
    memory.add_turn("assistant", text)   # record the reply too, so the NEXT turn sees it
    return text


if __name__ == "__main__":
    # Both objects created ONCE, before the loop starts, and passed into
    # every run_turn() call -- the same "create outside, mutate inside"
    # pattern as Stage 2's `messages` list, just wrapped in classes here.
    memory = Memory(client, MODEL)
    meter = CostMeter()
    while True:
        user_msg = input("> ")
        print(run_turn(memory, meter, user_msg))
        print(meter.report())   # running cost tally printed after every single reply
