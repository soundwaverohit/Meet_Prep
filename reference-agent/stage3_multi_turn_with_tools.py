"""
Stage 3 -- Combine both loops: multi-turn memory + tool use.
Every real tool-use agent needs TWO loops working together:
  - the per-turn loop (Week 2): keep calling the model and running tools
    until it stops asking for one and gives a final answer.
  - the cross-turn loop (Stage 2): keep the same `messages` list alive
    across multiple user inputs, so context survives between questions.
This file nests them: the per-turn `while` loop lives inside run_agent(),
the cross-turn state lives in the `messages` list created once in
__main__ and passed in on every call -- exactly the shape you'll use in
../support-agent-exercise/agent.py.

Run:  python stage3_multi_turn_with_tools.py
Try:  "What's 340 * 12?"  then  "Now divide that by 8."
      (the second question only makes sense if the agent remembers the
      first answer -- there's no other way for it to know what "that" is)
"""

import ast        # Python's own syntax-tree parser -- lets us evaluate math safely, without eval()
import operator   # gives us +, -, *, / as callable functions (operator.add, operator.mul, ...)

import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic()
MODEL = "claude-sonnet-5"
SYSTEM = "You are a helpful assistant with a calculator tool."
MAX_STEPS = 5   # safety cap: never loop more than 5 times chasing tool calls in a single turn

# The tool schema Claude sees. "input_schema" is JSON Schema -- it tells
# the model exactly what shape of input this tool expects, so it can
# generate a valid call instead of guessing.
CALCULATOR_SCHEMA = {
    "name": "calculator",                 # the identifier Claude uses when it wants to call this tool
    "description": "Evaluate a basic arithmetic expression (+, -, *, /, parentheses).",
    "input_schema": {
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "e.g. '340 * 12'"},
        },
        "required": ["expression"],       # Claude must supply "expression" -- no optional fields here
    },
}
TOOLS = [CALCULATOR_SCHEMA]   # the list passed to messages.create(tools=...) -- can hold multiple tools

# Maps each AST operator node type to the actual Python function that
# performs it. This whitelist is the safety mechanism: only +, -, *, /
# are reachable, so a malicious expression can't do anything else.
_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
}


def _safe_eval(node):
    # Recursively walks the parsed expression tree. A raw number just
    # returns its value; a binary operation (a + b, a * b, ...) looks up
    # the matching function in _OPS and applies it to the recursively
    # evaluated left/right sides. Anything not matching either shape
    # (function calls, attribute access, imports, etc.) raises instead
    # of executing -- that's what makes this safe to run on model output.
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    raise ValueError("unsupported expression")


def calculator(expression: str) -> str:
    # This is the actual Python function that runs when Claude calls the
    # "calculator" tool. `ast.parse(..., mode="eval")` turns the string
    # into a tree without executing anything; `.body` is the root
    # expression node, which _safe_eval() then walks.
    try:
        return str(_safe_eval(ast.parse(expression, mode="eval").body))
    except Exception as exc:
        # Tool errors are returned as text, not raised -- Claude needs to
        # SEE the failure to recover (e.g. try a different expression),
        # so a Python exception here would crash the whole script instead.
        return f"error: {exc}"


def run_agent(messages: list[dict], user_msg: str) -> str:
    # Cross-turn (Stage 2's mechanic): append onto the SAME list object
    # passed in from __main__, so this turn builds on every prior one.
    messages.append({"role": "user", "content": user_msg})

    # Per-turn (Week 2's mechanic): this loop keeps calling the model
    # and feeding tool results back until it gets a final text answer,
    # or MAX_STEPS is hit as a safety valve against infinite tool-calling.
    for _ in range(MAX_STEPS):
        resp = client.messages.create(
            model=MODEL, max_tokens=1024, system=SYSTEM, tools=TOOLS, messages=messages,
        )
        # The assistant's full response (which may include tool_use
        # blocks) gets appended to history immediately, BEFORE we've
        # even handled the tool call -- the API requires every tool_use
        # block to be followed by a matching tool_result later, so this
        # response has to already be in `messages` when we send that.
        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason != "tool_use":
            # The model gave a final answer instead of asking for a tool
            # -- extract the text and stop looping.
            return next((b.text for b in resp.content if b.type == "text"), "")

        # stop_reason == "tool_use": the model wants to call one or more
        # tools before it can answer. resp.content is a mix of text and
        # tool_use blocks -- we only act on the tool_use ones.
        tool_results = []
        for block in resp.content:
            if block.type == "tool_use":
                # block.input is the arguments Claude generated, already
                # parsed into a dict matching input_schema -- **block.input
                # unpacks it as keyword arguments to calculator().
                result = calculator(**block.input)
                # tool_use_id links this result back to the specific
                # tool_use block that requested it -- required so the API
                # knows which call each result answers.
                tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
        # All tool results for this round go in ONE user message, then we
        # loop back to the top and call the model again with the results
        # now visible in history.
        messages.append({"role": "user", "content": tool_results})

    return "[stopped: hit MAX_STEPS]"


if __name__ == "__main__":
    messages: list[dict] = []   # created once, mutated across every turn -- Stage 2's pattern again
    while True:
        user_msg = input("> ")
        print(run_agent(messages, user_msg))
