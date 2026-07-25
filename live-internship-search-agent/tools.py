"""
Tools for the Live Internship Search Agent.

Two tiers of "search" on purpose:
  - search_saved_internships looks ONLY at what's already in
    data/internships.json -- free, instant, no network call.
  - web_search is Anthropic's own BUILT-IN server-side tool -- there is
    no Python function for it in this file at all. It's declared
    directly in agent.py's TOOLS list and Anthropic's own infrastructure
    executes it; the results just show up as content blocks in the
    response. save_internship is what turns one of those real results
    into a permanent row in data/internships.json.
See agent.py's system prompt for the policy on which tier the agent
should reach for, and when.
"""

import json                  # reads/writes the internships.json file
import os                    # builds filesystem paths that work regardless of the current working directory
from datetime import date    # for date_added -- computed here in code, never left to the model to guess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))       # the folder this file lives in, as an absolute path
DATA_DIR = os.path.join(BASE_DIR, "data")                    # BASE_DIR/data
INTERNSHIPS_PATH = os.path.join(DATA_DIR, "internships.json")  # the one file this whole module reads and writes


# ── Schemas ──────────────────────────────────────────────────────────────
# There is deliberately NO schema here for "web_search" -- that's
# Anthropic's built-in tool, declared in agent.py as
# {"type": "web_search_20260209", "name": "web_search"}. We never write
# or dispatch a Python function for it; only the three tools below are
# ours to implement.

SEARCH_SAVED_INTERNSHIPS_SCHEMA = {                    # tool definition dict passed to messages.create(tools=[...])
    "name": "search_saved_internships",                # identifier the model calls
    "description": (                                    # tells the model this is the LOCAL, cheap option
        "Search internships ALREADY SAVED in data/internships.json -- this "
        "is a local, free, instant lookup. Use this for any question about "
        "internships already found (filtering, follow-up questions, "
        "'show me the remote ones', etc). This does NOT go out to the "
        "internet -- for that, see the separate web_search tool."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Keywords, e.g. 'machine learning' or 'remote'"},
            "remote_only": {"type": "boolean", "description": "Only return remote listings. Default false."},
            "paid_only": {"type": "boolean", "description": "Only return paid listings. Default false."},
        },
        "required": ["query"],                          # only query is mandatory
    },
}

SAVE_INTERNSHIP_SCHEMA = {                              # tool definition for persisting ONE real listing
    "name": "save_internship",
    "description": (                                    # explicitly tells the model this is for REAL data only
        "Save ONE real internship listing, found via web_search, into "
        "data/internships.json permanently. Only call this after a live "
        "web_search -- never invent an internship that wasn't actually "
        "found. Skips automatically if the same company+role+location is "
        "already saved."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "company": {"type": "string"},
            "role": {"type": "string"},
            "location": {"type": "string", "description": "e.g. 'San Francisco, CA' or 'Remote'"},
            "remote": {"type": "boolean"},
            "paid": {"type": "boolean"},
            "stipend_usd_per_month": {
                "type": ["number", "null"],              # union type -- a number if known, explicit null if not
                "description": "Monthly stipend in USD if known, otherwise null.",
            },
            "focus_area": {"type": "string", "description": "e.g. 'software engineering', 'marketing'"},
            "deadline": {"type": "string", "description": "YYYY-MM-DD if known, otherwise 'unknown'."},
            "note": {"type": "string", "description": "1-2 sentence summary of what makes this listing notable."},
            "source_url": {"type": "string", "description": "The URL where this listing was found."},
        },
        "required": [                                    # everything except the stipend must be supplied
            "company", "role", "location", "remote", "paid",
            "focus_area", "deadline", "note", "source_url",
        ],
    },
}

LIST_SAVED_INTERNSHIPS_SCHEMA = {                       # tool definition for a full unfiltered dump
    "name": "list_saved_internships",
    "description": "List every internship currently saved in data/internships.json, unfiltered.",
    "input_schema": {"type": "object", "properties": {}, "required": []},  # takes no arguments at all
}


# ── data access ──────────────────────────────────────────────────────────

def _load() -> list[dict]:
    with open(INTERNSHIPS_PATH, encoding="utf-8") as f:   # opens the file, auto-closes when the block exits
        return json.load(f)["internships"]                # parses JSON, returns just the list under "internships"


def _save_all(internships: list[dict]) -> None:
    with open(INTERNSHIPS_PATH, "w", encoding="utf-8") as f:   # "w" truncates and rewrites the whole file
        json.dump({"internships": internships}, f, indent=2)   # writes the FULL updated list back, pretty-printed


def _next_id(internships: list[dict]) -> str:
    # Simple scheme: "REAL-001", "REAL-002", ... based on current count.
    # {:03d} zero-pads to 3 digits.
    return f"REAL-{len(internships) + 1:03d}"


def _is_duplicate(internships: list[dict], company: str, role: str, location: str) -> bool:
    # Lowercase + strip everything before comparing, so "BrightPath AI"
    # and " brightpath ai " are treated as the same key.
    key = (company.strip().lower(), role.strip().lower(), location.strip().lower())
    return any(                                            # True if ANY existing entry matches the key
        (i["company"].strip().lower(), i["role"].strip().lower(), i["location"].strip().lower()) == key
        for i in internships
    )


# ── tools ────────────────────────────────────────────────────────────────

def search_saved_internships(query: str, remote_only: bool = False, paid_only: bool = False) -> str:
    internships = _load()                                  # everything currently saved
    query_words = set(query.lower().split())                # e.g. "remote software" -> {"remote", "software"}

    matches = []                                             # (score, listing) pairs that pass the filters and match
    for listing in internships:                              # check every saved listing
        if remote_only and not listing["remote"]:            # hard filter: drop non-remote if remote_only requested
            continue
        if paid_only and not listing["paid"]:                # hard filter: drop unpaid if paid_only requested
            continue
        haystack = f"{listing['role']} {listing['focus_area']} {listing['note']}".lower()  # searchable text
        score = sum(1 for w in query_words if w in haystack)  # how many query words appear
        if score > 0:                                         # only keep listings that matched something
            matches.append((score, listing))

    if not internships:                                       # nothing saved AT ALL yet, distinct message
        return "No internships saved yet. Say 'search for [something]' to have me look on the internet."
    if not matches:                                           # something is saved, just nothing matched THIS query
        return f"Nothing saved matches query='{query}' (remote_only={remote_only}, paid_only={paid_only})."

    matches.sort(key=lambda t: t[0], reverse=True)            # best matches first
    lines = []
    for _, listing in matches:                                # build one readable line per match
        if listing["paid"] and listing.get("stipend_usd_per_month"):
            pay = f"paid ${listing['stipend_usd_per_month']}/mo"   # known stipend amount
        elif listing["paid"]:
            pay = "paid"                                       # paid, but amount unknown
        else:
            pay = "unpaid"
        lines.append(
            f"{listing['id']}: {listing['role']} at {listing['company']} "
            f"({listing['location']}, {'remote' if listing['remote'] else 'onsite'}, {pay}, "
            f"deadline {listing['deadline']}) -- {listing['note']}"
        )
    return "\n".join(lines)                                   # one listing per line


def save_internship(
    company: str,
    role: str,
    location: str,
    remote: bool,
    paid: bool,
    focus_area: str,
    deadline: str,
    note: str,
    source_url: str,
    stipend_usd_per_month: float | None = None,   # the one optional field -- defaults to None if omitted
) -> str:
    internships = _load()                                     # current saved list, before this new entry

    if _is_duplicate(internships, company, role, location):    # already have this exact company+role+location
        return f"Already saved: {role} at {company} ({location}) -- skipped duplicate."

    entry = {                                                  # the new row, matching internships.json's schema
        "id": _next_id(internships),                            # e.g. "REAL-001"
        "company": company,
        "role": role,
        "location": location,
        "remote": remote,
        "paid": paid,
        "stipend_usd_per_month": stipend_usd_per_month,
        "focus_area": focus_area,
        "deadline": deadline,
        "note": note,
        "source_url": source_url,
        "date_added": date.today().isoformat(),                 # computed HERE in code -- never trust the model's guess at "today"
    }
    internships.append(entry)                                  # add the new entry to the in-memory list
    _save_all(internships)                                     # write the WHOLE updated list back to disk
    return f"Saved {entry['id']}: {role} at {company} ({location}) to data/internships.json."


def list_saved_internships() -> str:
    internships = _load()
    if not internships:                                        # empty list -- nothing to show
        return "No internships saved yet."
    lines = []
    for listing in internships:                                 # one summary line per saved entry
        lines.append(
            f"{listing['id']}: {listing['role']} at {listing['company']} "
            f"({listing['location']}, added {listing['date_added']})"
        )
    return "\n".join(lines)


# ── dispatch ─────────────────────────────────────────────────────────────

_HANDLERS = {                                                   # maps tool name (string) -> the function that implements it
    "search_saved_internships": search_saved_internships,
    "save_internship": save_internship,
    "list_saved_internships": list_saved_internships,
}


def dispatch(name: str, tool_input: dict) -> str:
    """Route a tool_use block to the matching function. Never raises."""
    handler = _HANDLERS.get(name)                                # None if name isn't one of our three tools
    if handler is None:
        return f"error: unknown tool '{name}'"                   # tell the model, don't crash
    try:
        return handler(**tool_input)                              # unpack tool_input's keys as keyword arguments
    except TypeError as exc:                                       # raised if tool_input's keys don't match the function's params
        return f"error: bad arguments for '{name}' ({exc})"


def extract_text(resp) -> str:
    """First text block in a response."""
    for block in resp.content:                                    # resp.content can hold text, tool_use, and (with
        if block.type == "text":                                   # web_search enabled) server_tool_use /
            return block.text                                       # web_search_tool_result blocks too
    return "[no text content in response]"
