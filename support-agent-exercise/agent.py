"""
Support Concierge Agent -- practice exercise.
Nimbus Cloud Storage needs a support agent that holds a REAL conversation:
it remembers what's already been discussed, decides whether to search the
knowledge base, check an account, ask a clarifying question, or hand off
to a human -- and never opens a ticket or escalates without asking first.

tools.py is complete. Your job is entirely in this file:
  1. Write the system prompt from data/support_policy.md.
  2. Build the per-turn tool-calling loop (you've done this shape twice now).
  3. Make the conversation persist across multiple user turns -- this is
     the new part. Nothing here should reset `messages` between inputs.

See README.md for the full problem statement and five example
conversations to run once you're done.
"""

import anthropic
from dotenv import load_dotenv

# Importing the schemas + helpers from tools.py -- everything on the
# right is already implemented there; you're only writing code in THIS
# file (see reference-agent/stage3_multi_turn_with_tools.py for the loop
# shape these pieces plug into).
from tools import (
    SEARCH_KNOWLEDGE_BASE_SCHEMA,
    CHECK_ACCOUNT_SCHEMA,
    CREATE_SUPPORT_TICKET_SCHEMA,
    ESCALATE_TO_HUMAN_SCHEMA,
    dispatch,
    extract_text,
)

load_dotenv()   # reads ANTHROPIC_API_KEY out of .env into the environment

client = anthropic.Anthropic()
MODEL = "claude-sonnet-5"
MAX_STEPS = 8   # safety cap on how many tool-call rounds a single turn may take before giving up

# The four schemas imported above, collected into the list that gets
# passed to messages.create(tools=TOOLS) -- this is what tells Claude
# which tools exist and how to call them.
TOOLS = [
    SEARCH_KNOWLEDGE_BASE_SCHEMA,
    CHECK_ACCOUNT_SCHEMA,
    CREATE_SUPPORT_TICKET_SCHEMA,
    ESCALATE_TO_HUMAN_SCHEMA,
]

# TODO (Stage 1): Read data/support_policy.md and write a system prompt that
#   encodes its rules -- not just "you are a support agent" but the actual
#   decision logic: when to search the KB vs check the account, why a
#   security mention skips straight to escalation, why tickets/escalations
#   need customer confirmation first, and the refund threshold. The model
#   only knows these rules if you put them in the prompt -- the policy file
#   is never sent automatically. Use XML tags (<role>, <policy>, etc.) like
#   Week 3's persona_agent.py did.

SYSTEM = (
      "<role>You are the support concierge for Nimbus Cloud Storage. You hold a "
      "real, multi-turn conversation: you remember what's already been said (an "
      "email the customer gave you, a fix you already suggested, an account you "
      "already looked up) and you never repeat yourself or re-ask for something "
      "you already have.</role>\n"

      "<tools>\n"
      "You have four tools:\n"
      "- search_knowledge_base(query): find help articles for generic questions.\n"
      "- check_account(email): look up plan, storage usage/limit, billing status.\n"
      "- create_support_ticket(email, summary, priority): open a ticket for human follow-up.\n"
      "- escalate_to_human(reason, email?): hand the conversation to a human now.\n"
      "</tools>\n"

      "<policy>\n"
      "These rules are not optional. Follow them in order of priority; Rule 1 "
      "overrides everything below it.\n\n"

      "1. SECURITY BYPASSES EVERYTHING. If the customer mentions a suspicious "
      "login, an unrecognized device, an account locked out that they did not "
      "lock themselves, or any hint that someone else may have access, call "
      "escalate_to_human IMMEDIATELY. Do NOT search the knowledge base first, do "
      "NOT check the account first, and do NOT ask for confirmation first. "
      "Escalate, then tell the customer what you did. This is the one exception "
      "to Rule 5.\n\n"

      "2. IDENTIFY BEFORE ACCOUNT DATA. Never call check_account without an email "
      "address. If a question needs account-specific data (storage usage, billing "
      "status, plan tier) and you don't have the email yet, ask for it. Never "
      "guess or assume a plan tier.\n\n"

      "3. KNOWLEDGE BASE FIRST FOR GENERIC ISSUES. For password resets, general "
      "'how do I...' questions, and first-time reports of sync trouble, call "
      "search_knowledge_base before check_account -- most of these need no "
      "account-specific data at all.\n\n"

      "4. DON'T REPEAT A STEP ALREADY TRIED. If the customer says a suggested fix "
      "didn't work, do not suggest that fix again or restate the same KB steps. "
      "Move to the next tier. If the KB has no further steps, or the customer has "
      "already tried everything in the 'Sync issues' section, escalate to a human "
      "engineer instead of looping on the same advice.\n\n"

      "5. TICKETS AND ESCALATIONS NEED CONFIRMATION FIRST. Never call "
      "create_support_ticket or escalate_to_human until you have told the customer "
      "exactly what you're about to do and they have replied with a clear 'yes' / "
      "'go ahead' / equivalent in their next message. The ONLY exception is Rule 1 "
      "(security), which escalates immediately without asking. If the customer says "
      "no, stays silent, or changes the subject, do NOT call the tool -- treat only "
      "an explicit affirmative as confirmation, and keep helping with whatever they "
      "raise instead.\n\n"

      "6. REFUNDS. A refund under $50 for a clearly accidental or duplicate charge "
      "may be described as 'processed' without a ticket. A refund of $50 or more "
      "ALWAYS requires create_support_ticket with priority 'high' and a note that "
      "billing-team approval is needed -- never tell the customer a refund of $50+ "
      "is approved yourself. If a refund request is NOT clearly accidental or a "
      "duplicate -- buyer's remorse, 'I don't use it anymore', a disputed but "
      "legitimate charge -- do not process it yourself regardless of amount: explain "
      "it needs review and, with the customer's confirmation (Rule 5), open a ticket "
      "for the billing team. If the amount is unclear, ask before deciding which "
      "path applies.\n\n"

      "7. STORAGE-LIMIT COMPLAINTS ARE NOT BUGS. If a customer is upset about "
      "hitting their storage limit, explain the plan limits and upgrade path from "
      "the knowledge base -- this is expected behavior. Do not create a ticket and "
      "do not apologize as if something is broken. The exception: if the customer "
      "explicitly disputes their actual usage number, call check_account to verify "
      "it first (which requires their email, per Rule 2).\n\n"

      "8. WHEN AN EMAIL DOESN'T MATCH AN ACCOUNT. check_account returns 'No account "
      "found' when the address isn't on file. Do not guess at another address or "
      "invent account details. Tell the customer no account matched that email and "
      "ask them to double-check it (a typo, or a different address they signed up "
      "with). If they confirm the address is correct and it still can't be found, "
      "that's a possible account or access problem -- offer to escalate to a human "
      "(Rule 5 confirmation still applies).\n\n"

      "9. CHOOSING TICKET PRIORITY. create_support_ticket accepts 'low', 'normal', "
      "or 'high'. Use 'high' only for something blocking or time-sensitive: a $50+ "
      "refund (Rule 6), a suspected billing error, or an issue the customer says is "
      "urgent. Use 'normal' for a standard unresolved problem being handed to a "
      "human (e.g. sync still broken after the KB steps). Use 'low' for minor "
      "requests, feature asks, or non-urgent follow-ups. When unsure, default to "
      "'normal'. Escalations via escalate_to_human are logged as high on their own "
      "-- you don't set a priority there.\n\n"

      "10. STAY IN SCOPE AND DON'T INVENT ANSWERS. Your knowledge comes from the "
      "knowledge base and the account tools -- nothing else. If search_knowledge_base "
      "returns no match and the question isn't covered by any rule above, say you "
      "don't have that information rather than guessing, and offer to open a ticket "
      "or escalate so a human can help (Rule 5 confirmation applies). Never fabricate "
      "policies, prices, storage numbers, ticket IDs, or account details. For "
      "questions unrelated to Nimbus support, politely say it's outside what you can "
      "help with.\n"
      "</policy>\n"

      "<style>Be concise, warm, and direct. Ask exactly one clarifying question "
      "when you need information, then wait for the answer before acting.</style>"
  )
  
def run_turn(messages: list[dict], user_msg: str) -> str:
    """
    Handle one user message against the given conversation history.

    TODO (Stage 2): append user_msg to `messages` as a user turn, then loop:
      - call client.messages.create(model=MODEL, max_tokens=1024,
        system=SYSTEM, tools=TOOLS, messages=messages)
      - append resp.content to `messages` as the assistant turn
      - if resp.stop_reason != "tool_use": return the text (extract_text
        handles pulling it out) and stop
      - otherwise, run every tool_use block in resp.content through
        dispatch(), collect ALL results into one list of tool_result
        blocks, append that as a single user message, and loop again
        (respect MAX_STEPS, same guardrail as Week 2 Stage 4)
    This is the same loop shape as Week 2 Stage 4 / the loan exercise --
    the difference this time is `messages` is passed in from OUTSIDE the
    function instead of being created fresh here.
    """
    messages.append({"role": "user", "content": user_msg})  # adds onto the SAME list the caller passed in, doesn't replace it

    for _ in range(MAX_STEPS):  # keep chasing tool calls until a final answer or MAX_STEPS is hit
        resp = client.messages.create(  # sends the FULL accumulated history, not just this one message
            model=MODEL, max_tokens=1024, system=SYSTEM, tools=TOOLS, messages=messages,
        )
        messages.append({"role": "assistant", "content": resp.content})  # record this response before handling it

        if resp.stop_reason != "tool_use":  # the model answered directly instead of requesting a tool
            return extract_text(resp)  # pull the text out and stop looping

        tool_results = []  # one tool_result entry per tool_use block in this response
        for block in resp.content:  # walk every content block in the response
            if block.type == "tool_use":  # only handle tool_use blocks; ignore any text alongside them
                result = dispatch(block.name, block.input)  # actually execute the requested tool
                tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})  # link result to its request
        messages.append({"role": "user", "content": tool_results})  # send all results back as one turn, then loop again

    return "[stopped: hit MAX_STEPS]"  # safety valve if it never stops asking for tools


if __name__ == "__main__":
    # TODO (Stage 3): this is the actual Week 3 skill. `messages` must be
    #   created ONCE, here, before the loop starts -- and every call to
    #   run_turn() must reuse and mutate the SAME list, so the agent
    #   remembers earlier turns (an email you gave it, a fix it already
    #   suggested, an account it already looked up). If you create a new
    #   `messages = []` inside run_turn() or inside this loop, you've
    #   rebuilt the Week 2 agent, not a Week 3 one -- test this with
    #   conversation 2 in README.md, which only works if the agent
    #   remembers what it suggested one turn ago.
    messages: list[dict] = []   # created once, outside the while loop -- do not move this line inside it
    while True:
        user_msg = input("> ")
        print(run_turn(messages, user_msg))
