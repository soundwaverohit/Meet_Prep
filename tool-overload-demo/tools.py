"""
Shared tool implementations for THREE unrelated domains -- support,
internship search, arithmetic -- used two different ways:
  - kitchen_sink_agent.py: ONE agent holds all 7 tools + one merged
    system prompt at once, every request.
  - orchestrator_agent.py: a router delegates to three focused
    specialists, each seeing only ITS domain's tools and prompt.
Same tools, same data, same model -- the only variable is how much of
this an agent sees on any single request. See README.md.
"""

import ast
import json
import operator
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

_TICKETS: list[dict] = []
_STATUS: dict[str, str] = {}


def reset_state() -> None:
    """Clears in-memory state -- compare.py calls this between test prompts."""
    _TICKETS.clear()
    _STATUS.clear()


# ── Support domain (4 tools) ────────────────────────────────────────────

SEARCH_KNOWLEDGE_BASE_SCHEMA = {
    "name": "search_knowledge_base",
    "description": "Search Nimbus support help articles (password reset, sync issues, storage limits, billing, security).",
    "input_schema": {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
}

CHECK_ACCOUNT_SCHEMA = {
    "name": "check_account",
    "description": "Look up a Nimbus customer account by email.",
    "input_schema": {
        "type": "object",
        "properties": {"email": {"type": "string"}},
        "required": ["email"],
    },
}

CREATE_SUPPORT_TICKET_SCHEMA = {
    "name": "create_support_ticket",
    "description": "Open a Nimbus support ticket. Only after the customer confirms.",
    "input_schema": {
        "type": "object",
        "properties": {
            "email": {"type": "string"},
            "summary": {"type": "string"},
            "priority": {"type": "string", "enum": ["low", "normal", "high"]},
        },
        "required": ["email", "summary", "priority"],
    },
}

ESCALATE_TO_HUMAN_SCHEMA = {
    "name": "escalate_to_human",
    "description": "Immediately hand a Nimbus conversation to a human. Use for security issues without asking first.",
    "input_schema": {
        "type": "object",
        "properties": {"email": {"type": "string"}, "reason": {"type": "string"}},
        "required": ["reason"],
    },
}


def _load_kb_sections() -> list[tuple[str, str]]:
    path = os.path.join(DATA_DIR, "knowledge_base.md")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    sections, heading, body = [], None, []
    for line in text.splitlines():
        if line.startswith("## "):
            if heading:
                sections.append((heading, "\n".join(body).strip()))
            heading, body = line[3:].strip(), []
        elif line.startswith("# "):
            continue
        else:
            body.append(line)
    if heading:
        sections.append((heading, "\n".join(body).strip()))
    return sections


def search_knowledge_base(query: str) -> str:
    sections = _load_kb_sections()
    words = set(query.lower().split())
    scored = [(sum(1 for w in words if w in f"{h} {b}".lower()), h, b) for h, b in sections]
    scored = [s for s in scored if s[0] > 0]
    if not scored:
        return f"No knowledge base articles matched '{query}'."
    scored.sort(key=lambda t: t[0], reverse=True)
    return "\n\n".join(f"## {h}\n{b}" for _, h, b in scored[:2])


def check_account(email: str) -> str:
    path = os.path.join(DATA_DIR, "accounts.json")
    with open(path, encoding="utf-8") as f:
        accounts = json.load(f)
    record = accounts.get(email)
    if record is None:
        return f"No account found for '{email}'."
    return f"Account for {email}:\n" + "\n".join(f"{k}: {v}" for k, v in record.items())


def create_support_ticket(email: str, summary: str, priority: str) -> str:
    ticket_id = f"TICKET-{1000 + len(_TICKETS) + 1}"
    _TICKETS.append({"id": ticket_id, "email": email, "summary": summary, "priority": priority})
    return f"Created {ticket_id} (priority: {priority}) for {email}: {summary}"


def escalate_to_human(reason: str, email: str = "") -> str:
    ticket_id = f"TICKET-{1000 + len(_TICKETS) + 1}"
    _TICKETS.append({"id": ticket_id, "email": email, "summary": reason, "priority": "high"})
    return f"Escalated ({ticket_id}, priority: high). Reason: {reason}"


# ── Internship domain (2 tools) ─────────────────────────────────────────

SEARCH_INTERNSHIPS_SCHEMA = {
    "name": "search_internships",
    "description": "Search saved internship listings by keyword.",
    "input_schema": {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
}

TRACK_STATUS_SCHEMA = {
    "name": "track_status",
    "description": "Record or look up a candidate's status on an internship ID. Use status='check' to just look up the current status.",
    "input_schema": {
        "type": "object",
        "properties": {
            "internship_id": {"type": "string"},
            "status": {
                "type": "string",
                "enum": ["shortlisted", "applied", "rejected", "not_interested", "check"],
            },
        },
        "required": ["internship_id", "status"],
    },
}


def _load_internships() -> list[dict]:
    path = os.path.join(DATA_DIR, "internships.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)["internships"]


def search_internships(query: str) -> str:
    words = set(query.lower().split())
    matches = []
    for listing in _load_internships():
        haystack = f"{listing['role']} {listing['focus_area']} {listing['note']}".lower()
        score = sum(1 for w in words if w in haystack)
        if score > 0:
            matches.append((score, listing))
    if not matches:
        return f"No internships matched '{query}'."
    matches.sort(key=lambda t: t[0], reverse=True)
    return "\n".join(f"{l['id']}: {l['role']} at {l['company']} ({l['location']})" for _, l in matches)


def track_status(internship_id: str, status: str) -> str:
    if status == "check":
        current = _STATUS.get(internship_id)
        return f"{internship_id} status: {current or 'not tracked'}"
    _STATUS[internship_id] = status
    return f"Tracked {internship_id} as '{status}'."


# ── Calculator domain (1 tool) ──────────────────────────────────────────

CALCULATOR_SCHEMA = {
    "name": "calculator",
    "description": "Evaluate a basic arithmetic expression (+, -, *, /).",
    "input_schema": {
        "type": "object",
        "properties": {"expression": {"type": "string"}},
        "required": ["expression"],
    },
}

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


def _safe_eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    raise ValueError("unsupported expression")


def calculator(expression: str) -> str:
    try:
        return str(_safe_eval(ast.parse(expression, mode="eval").body))
    except Exception as exc:
        return f"error: {exc}"


# ── dispatch ─────────────────────────────────────────────────────────────

ALL_HANDLERS = {
    "search_knowledge_base": search_knowledge_base,
    "check_account": check_account,
    "create_support_ticket": create_support_ticket,
    "escalate_to_human": escalate_to_human,
    "search_internships": search_internships,
    "track_status": track_status,
    "calculator": calculator,
}


def dispatch(name: str, tool_input: dict) -> str:
    handler = ALL_HANDLERS.get(name)
    if handler is None:
        return f"error: unknown tool '{name}'"
    try:
        return handler(**tool_input)
    except TypeError as exc:
        return f"error: bad arguments for '{name}' ({exc})"


def extract_text(resp) -> str:
    for block in resp.content:
        if block.type == "text":
            return block.text
    return "[no text content in response]"


# ── grouped for convenience -- kitchen_sink_agent.py uses ALL_TOOLS,
# orchestrator_agent.py's specialists each use exactly one of the three ──

SUPPORT_TOOLS = [SEARCH_KNOWLEDGE_BASE_SCHEMA, CHECK_ACCOUNT_SCHEMA, CREATE_SUPPORT_TICKET_SCHEMA, ESCALATE_TO_HUMAN_SCHEMA]
INTERNSHIP_TOOLS = [SEARCH_INTERNSHIPS_SCHEMA, TRACK_STATUS_SCHEMA]
CALCULATOR_TOOLS = [CALCULATOR_SCHEMA]
ALL_TOOLS = SUPPORT_TOOLS + INTERNSHIP_TOOLS + CALCULATOR_TOOLS
