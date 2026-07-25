"""
Tools for the Internship Finder demo. Complete and ready to use -- this
demo is about the multi-turn vs. stateless CONTRAST (see
stateless_agent.py vs multi_turn_agent.py), not tool design.
"""

import json  # lets us parse internships.json into Python dicts/lists
import os    # lets us build filesystem paths that work regardless of the current working directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # the folder this file (tools.py) lives in, as an absolute path
DATA_DIR = os.path.join(BASE_DIR, "data")               # BASE_DIR/data -- where internships.json lives

# In-memory tracker: internship_id -> status ("shortlisted" | "applied" |
# "rejected" | "not_interested"). Module-level state, same pattern as the
# support-agent-exercise's ticket list -- persists for the life of the
# running process only.
_STATUS: dict[str, str] = {}  # starts empty; entries are added by track_status() as the conversation happens


def reset_status() -> None:
    """Clear all tracked statuses. run_demo.py calls this between the
    stateless and multi-turn runs so neither leaks into the other."""
    _STATUS.clear()  # empties the dict in place so both demo runs start from zero tracked statuses


# ── Schemas ──────────────────────────────────────────────────────────────

SEARCH_INTERNSHIPS_SCHEMA = {  # the tool definition dict passed to messages.create(tools=[...])
    "name": "search_internships",  # the exact string Claude uses when it decides to call this tool
    "description": (  # tells the model what this tool does and when to reach for it
        "Search internship listings by keyword, with optional remote-only "
        "and paid-only filters. Returns short summaries -- call "
        "get_internship_details for the full listing on any one result."
    ),
    "input_schema": {  # JSON Schema describing exactly what arguments this tool accepts
        "type": "object",  # arguments always arrive as a JSON object, never a bare string/array
        "properties": {  # each key here is one argument the model may supply
            "query": {"type": "string", "description": "Keywords, e.g. 'machine learning' or 'software engineering'"},  # free-text keyword search
            "remote_only": {"type": "boolean", "description": "Only return remote listings. Default false."},  # optional hard filter
            "paid_only": {"type": "boolean", "description": "Only return paid listings. Default false."},  # optional hard filter
        },
        "required": ["query"],  # only "query" must be supplied; the two booleans can be omitted
    },
}

GET_INTERNSHIP_DETAILS_SCHEMA = {  # tool definition for looking up one listing's full details
    "name": "get_internship_details",  # identifier the model calls
    "description": "Get the full listing for one internship by ID.",  # one-line purpose statement
    "input_schema": {
        "type": "object",
        "properties": {
            "internship_id": {"type": "string", "description": "e.g. 'INT-005'"},  # the only argument this tool needs
        },
        "required": ["internship_id"],  # mandatory -- there's no "get all details" mode
    },
}

TRACK_STATUS_SCHEMA = {  # tool definition for recording a candidate's decision on a listing
    "name": "track_status",  # identifier the model calls
    "description": (  # explains both what it does and WHEN to call it
        "Record the candidate's status on a specific internship: "
        "shortlisted, applied, rejected, or not_interested. Call this "
        "whenever the candidate makes a decision about a listing."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "internship_id": {"type": "string"},  # which listing this status applies to
            "status": {
                "type": "string",
                "enum": ["shortlisted", "applied", "rejected", "not_interested"],  # restricts the model to exactly these 4 values
            },
        },
        "required": ["internship_id", "status"],  # both fields are mandatory -- can't track a status without an ID
    },
}

LIST_TRACKED_SCHEMA = {  # tool definition for listing everything tracked so far
    "name": "list_tracked",  # identifier the model calls
    "description": "List every internship with a tracked status so far, and what that status is.",
    "input_schema": {"type": "object", "properties": {}, "required": []},  # takes no arguments at all
}


# ── data access ──────────────────────────────────────────────────────────

def _load_internships() -> list[dict]:
    # Re-reads the JSON file on every call rather than caching it -- fine
    # for a 12-row demo dataset; a real system would cache or use a DB.
    path = os.path.join(DATA_DIR, "internships.json")  # full path to the data file
    with open(path, encoding="utf-8") as f:  # opens the file, auto-closes when the block exits
        return json.load(f)["internships"]  # parses the JSON and returns just the list under the "internships" key


def search_internships(query: str, remote_only: bool = False, paid_only: bool = False) -> str:
    listings = _load_internships()  # the full list of 12 listings, freshly loaded
    query_words = set(query.lower().split())  # e.g. "sync not working" -> {"sync", "not", "working"}

    matches = []  # will hold (score, listing) tuples for anything that passes the filters and matches at least one word
    for listing in listings:  # check every listing one at a time
        # Hard filters first -- these DROP a listing entirely, unlike the
        # keyword score below which only ranks what's left.
        if remote_only and not listing["remote"]:  # caller wants remote-only, but this listing isn't remote
            continue  # skip this listing entirely, move to the next one
        if paid_only and not listing["paid"]:  # caller wants paid-only, but this listing is unpaid
            continue  # skip this listing entirely
        haystack = f"{listing['role']} {listing['focus_area']} {listing['note']}".lower()  # all searchable text, lowercased
        score = sum(1 for w in query_words if w in haystack)  # count how many query words appear in the haystack
        if score > 0:  # only keep listings that matched at least one word
            matches.append((score, listing))  # remember the score alongside the listing for sorting later

    if not matches:  # nothing matched at all
        return f"No internships matched query='{query}' (remote_only={remote_only}, paid_only={paid_only})."

    matches.sort(key=lambda t: t[0], reverse=True)  # highest-scoring (most relevant) listings first
    lines = []  # will hold one formatted string per matching listing
    for _, listing in matches:  # the score itself isn't needed anymore, just the listing
        # If this listing already has a tracked status, surface it right
        # in the search results -- e.g. "[applied]" -- so the model (and
        # a human reading the transcript) can see it without a separate
        # get_internship_details call.
        status = _STATUS.get(listing["id"])  # None if this listing has never been tracked
        status_tag = f" [{status}]" if status else ""  # e.g. " [applied]", or "" if untracked
        lines.append(  # build one readable line for this listing
            f"{listing['id']}{status_tag}: {listing['role']} at {listing['company']} "
            f"({listing['location']}, {'remote' if listing['remote'] else 'onsite'}, "
            f"{'paid $' + str(listing['stipend_usd_per_month']) + '/mo' if listing['paid'] else 'unpaid'}, "
            f"deadline {listing['deadline']})"
        )
    return "\n".join(lines)  # one listing per line, joined into a single string


def get_internship_details(internship_id: str) -> str:
    for listing in _load_internships():  # scan every listing looking for a matching ID
        if listing["id"] == internship_id:  # found the one we want
            status = _STATUS.get(internship_id)  # None if never tracked
            lines = [f"{k}: {v}" for k, v in listing.items()]  # every field in the listing, one per line
            if status:  # only add this line if a status has actually been tracked
                lines.append(f"tracked_status: {status}")
            return "\n".join(lines)  # all fields (plus status, if any) as one multi-line string
    return f"No internship found with ID '{internship_id}'."  # loop finished without finding a match


def track_status(internship_id: str, status: str) -> str:
    _STATUS[internship_id] = status  # write (or overwrite) the status for this ID in the shared dict
    return f"Tracked {internship_id} as '{status}'."  # confirmation text the model sees as the tool result


def list_tracked() -> str:
    if not _STATUS:  # the dict is empty -- nothing has been tracked yet
        return "Nothing tracked yet."
    return "\n".join(f"{iid}: {status}" for iid, status in _STATUS.items())  # one "ID: status" line per tracked entry


# ── dispatch ─────────────────────────────────────────────────────────────

_HANDLERS = {  # maps each tool's string name to the actual Python function that implements it
    "search_internships": search_internships,
    "get_internship_details": get_internship_details,
    "track_status": track_status,
    "list_tracked": list_tracked,
}


def dispatch(name: str, tool_input: dict) -> str:
    """Route a tool_use block to the matching function. Never raises."""
    handler = _HANDLERS.get(name)  # None if the model somehow asked for a tool name we don't recognize
    if handler is None:
        return f"error: unknown tool '{name}'"  # tell the model, don't crash the script
    try:
        return handler(**tool_input)  # unpacks tool_input's keys as keyword arguments to the handler function
    except TypeError as exc:  # raised if tool_input's keys don't match the handler's expected parameters
        return f"error: bad arguments for '{name}' ({exc})"


def extract_text(resp) -> str:
    """First text block in a response."""
    for block in resp.content:  # resp.content is a list of blocks (text, tool_use, etc.)
        if block.type == "text":  # found the first text block
            return block.text
    return "[no text content in response]"  # fallback if somehow there's no text block at all
