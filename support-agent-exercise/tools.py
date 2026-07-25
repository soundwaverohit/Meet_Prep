"""
Tools for the Support Concierge Agent exercise.
All four tools are complete and ready to use -- this week's new skill is
the agent loop and decision logic in agent.py, not tool plumbing (you've
already built that twice: the Week 2 lab and the loan qualification
exercise). Read data/support_policy.md before touching agent.py; it tells
you exactly which tool to call when.
"""

import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # absolute path to this file's directory, wherever the script is run from
DATA_DIR = os.path.join(BASE_DIR, "data")               # .../support-agent-exercise/data, regardless of cwd

_TICKETS: list[dict] = []  # in-memory only -- resets each time the script runs; not written to disk


# ── Schemas ──────────────────────────────────────────────────────────────
# Each SCHEMA dict below is what gets passed to messages.create(tools=[...]).
# "name" is what the model calls when it wants this tool; "input_schema"
# is JSON Schema describing the exact shape of arguments it must supply.

SEARCH_KNOWLEDGE_BASE_SCHEMA = {
    "name": "search_knowledge_base",
    "description": (
        "Search the Nimbus support knowledge base for help articles matching "
        "a query. Use this for generic questions (password reset, sync issues, "
        "storage limits, billing, data recovery) before checking account-specific data."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What the customer is asking about, e.g. 'sync not working'",
            },
        },
        "required": ["query"],   # the model must always supply a query -- no optional args on this tool
    },
}

CHECK_ACCOUNT_SCHEMA = {
    "name": "check_account",
    "description": (
        "Look up a customer's account by email: plan, storage usage/limit, "
        "billing status. Only call this once you have the customer's email."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "email": {
                "type": "string",
                "description": "Customer's account email, e.g. 'alice@example.com'",
            },
        },
        "required": ["email"],
    },
}

CREATE_SUPPORT_TICKET_SCHEMA = {
    "name": "create_support_ticket",
    "description": (
        "Open a support ticket for a human to follow up on. Only call this "
        "AFTER the customer has confirmed they want a ticket opened -- never "
        "as the first response to an issue."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "email": {"type": "string", "description": "Customer's account email"},
            "summary": {"type": "string", "description": "One or two sentence summary of the issue"},
            "priority": {
                "type": "string",
                "enum": ["low", "normal", "high"],   # restricts the model to exactly these three values
                "description": "Ticket priority",
            },
        },
        "required": ["email", "summary", "priority"],   # all three fields are mandatory
    },
}

ESCALATE_TO_HUMAN_SCHEMA = {
    "name": "escalate_to_human",
    "description": (
        "Immediately hand the conversation off to a human agent. Use for "
        "security concerns (always, without asking first) or when you've "
        "exhausted the knowledge base and the issue is still unresolved."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "email": {"type": "string", "description": "Customer's account email, if known"},
            "reason": {"type": "string", "description": "Why this needs a human"},
        },
        "required": ["reason"],   # email is optional here -- a security report might come in before an email is known
    },
}


# ── search_knowledge_base ────────────────────────────────────────────────

def _load_kb_sections() -> list[tuple[str, str]]:
    # Reads the whole markdown file and splits it into (heading, body)
    # pairs by walking line-by-line and watching for "## " headings.
    path = os.path.join(DATA_DIR, "knowledge_base.md")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    sections = []
    heading, body = None, []   # `body` accumulates lines until the next heading (or end of file) closes the section
    for line in text.splitlines():
        if line.startswith("## "):
            if heading:   # we've hit a NEW heading -- flush the previous section before starting the next
                sections.append((heading, "\n".join(body).strip()))
            heading, body = line[3:].strip(), []   # line[3:] strips the leading "## "
        elif line.startswith("# "):
            continue   # skip the top-level "# Nimbus..." title -- it's not a section
        else:
            body.append(line)
    if heading:   # flush the final section after the loop ends (nothing triggers the flush above for the last one)
        sections.append((heading, "\n".join(body).strip()))
    return sections


def search_knowledge_base(query: str) -> str:
    """Keyword-match query against KB section headings + bodies; return the top matches."""
    sections = _load_kb_sections()
    query_words = set(query.lower().split())   # a set of lowercase words from the query, e.g. {"sync", "not", "working"}
    scored = []
    for heading, body in sections:
        haystack = f"{heading} {body}".lower()
        # Count how many query words appear anywhere in this section --
        # a crude relevance score, but good enough for a lab exercise.
        score = sum(1 for w in query_words if w in haystack)
        if score > 0:
            scored.append((score, heading, body))
    if not scored:
        return f"No knowledge base articles matched '{query}'."
    scored.sort(key=lambda t: t[0], reverse=True)   # highest score first
    return "\n\n".join(f"## {h}\n{b}" for _, h, b in scored[:2])   # top 2 matches only, reassembled as markdown


# ── check_account ────────────────────────────────────────────────────────

def check_account(email: str) -> str:
    path = os.path.join(DATA_DIR, "accounts.json")
    with open(path, encoding="utf-8") as f:
        accounts = json.load(f)   # parses the whole JSON file into a dict keyed by email
    record = accounts.get(email)  # .get() returns None instead of raising if the key is missing
    if record is None:
        return f"No account found for '{email}'."
    lines = [f"{k}: {v}" for k, v in record.items()]
    return f"Account for {email}:\n" + "\n".join(lines)


# ── create_support_ticket ────────────────────────────────────────────────

def create_support_ticket(email: str, summary: str, priority: str) -> str:
    # Ticket IDs are just "1000 + however many tickets already exist" --
    # simple and unique for the lifetime of one script run, which is all
    # this exercise needs (no persistence across restarts).
    ticket_id = f"TICKET-{1000 + len(_TICKETS) + 1}"
    _TICKETS.append({"id": ticket_id, "email": email, "summary": summary, "priority": priority})
    return f"Created {ticket_id} (priority: {priority}) for {email}: {summary}"


# ── escalate_to_human ────────────────────────────────────────────────────

def escalate_to_human(reason: str, email: str = "") -> str:
    # Escalation also creates a ticket behind the scenes (same _TICKETS
    # list, same ID scheme) so every hand-off is trackable the same way.
    ticket_id = f"TICKET-{1000 + len(_TICKETS) + 1}"
    _TICKETS.append({"id": ticket_id, "email": email, "summary": reason, "priority": "high"})
    return f"Escalated to a human support engineer ({ticket_id}, priority: high). Reason: {reason}"


# ── dispatch ─────────────────────────────────────────────────────────────

# A lookup table from tool name (string) to the actual Python function
# that implements it -- this is what lets dispatch() below route any
# tool_use block without a long if/elif chain.
_HANDLERS = {
    "search_knowledge_base": search_knowledge_base,
    "check_account": check_account,
    "create_support_ticket": create_support_ticket,
    "escalate_to_human": escalate_to_human,
}


def dispatch(name: str, tool_input: dict) -> str:
    """Route a tool_use block to the matching function. Never raises."""
    handler = _HANDLERS.get(name)
    if handler is None:
        return f"error: unknown tool '{name}'"   # the model asked for a tool that doesn't exist -- tell it, don't crash
    try:
        # tool_input is a dict like {"email": "...", "priority": "high"};
        # **tool_input unpacks it into keyword arguments matching the
        # handler function's parameter names.
        return handler(**tool_input)
    except TypeError as exc:
        # Raised if tool_input's keys don't match the function's
        # parameters (e.g. a missing required argument) -- again,
        # reported back as text instead of crashing the script.
        return f"error: bad arguments for '{name}' ({exc})"


def extract_text(resp) -> str:
    """First text block in a response."""
    for block in resp.content:
        if block.type == "text":
            return block.text
    return "[no text content in response]"
