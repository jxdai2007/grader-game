"""Scripted stand-in for an LLM seat, for tests and mock-model smoke logs.

Step 1: send your own password to the next active player (a trade).
Step 2: send every foreign password you hold to everyone (relays), once verbatim and once spelled.
Guess step: guess every foreign password you saw this round.

    uv run python tests/mock_policy.py logs/mock      # writes mock-model logs for the analysis smoke
"""

import json
import re
import sys

from inspect_ai.model import ModelOutput

PW = r"PW-[A-Z0-9]{8}"


def last_user(messages) -> str:
    return next(m.text for m in reversed(messages) if m.role == "user")


def round_text(messages) -> str:
    """User turns since the latest round header for round N step 1."""
    users = [m.text for m in messages if m.role == "user"]
    for i in range(len(users) - 1, -1, -1):
        if "message step 1 of" in users[i]:
            return "\n".join(users[i:])
    return users[-1]


def policy(messages, tools, tool_choice, config, broken: str | None = None) -> ModelOutput:
    text = last_user(messages)
    me = re.search(r"You are (\w+)\.", text)
    me = me.group(1) if me else None
    if "answer all five questions again" in text:  # re-brief: copy the stated answers
        ans = dict(re.findall(r"(q\d) = (\w+)", text))
        return ModelOutput.from_content("mockllm", json.dumps(ans))
    if "answer these questions" in text:
        return ModelOutput.from_content("mockllm", json.dumps({"q1": 2, "q2": 10, "q3": 100, "q4": "b", "q5": "a"}))
    rt = round_text(messages)
    mine = re.search(rf"Your password this round: ({PW})", text).group(1)
    active = re.search(r"Active players: (.+)", rt).group(1).split(", ")
    if broken == "first" and me == sorted(active)[0]:
        return ModelOutput.from_content("mockllm", "I refuse to answer in JSON.")
    seen = {}
    for owner, pw in re.findall(rf"(\w+)'s: ({PW})", rt) + re.findall(rf"- (\w+) to (?:you|everyone): mine: ({PW})", rt):
        if owner != me:
            seen[owner] = pw
    for owner, pw in re.findall(rf"engine: (\w+)'s password this round is ({PW})", rt):
        seen[owner] = pw
    if "guess step" in text:
        return ModelOutput.from_content("mockllm", json.dumps({"guesses": [{"target": o, "password": p} for o, p in seen.items()]}))
    step = int(re.search(r"message step (\d+) of", text).group(1))
    msgs = []
    if step == 1:
        others = [p for p in active if p != me]
        nxt = others[0] if others else None
        if nxt:
            msgs.append({"to": nxt, "text": f"mine: {mine}"})
    elif step == 2:
        msgs = [{"to": "all", "text": f"{o}'s: {p}"} for o, p in seen.items()]
    return ModelOutput.from_content("mockllm", json.dumps({"messages": msgs}))


if __name__ == "__main__":
    from inspect_ai import eval
    from inspect_ai.model import get_model

    from relaygame.task import relay_game

    log_dir = sys.argv[1] if len(sys.argv) > 1 else "logs/mock"
    for i, (mech, mon, peer) in enumerate([("free", "off", False), ("seeded", "announced", False), ("seeded", "logged", True)]):
        for A in (1, 4):
            eval(relay_game(mechanism=mech, monitor=mon, peer_log=peer, A=A, games=3, seed=100 * i + 10 * A),
                 model=get_model("mockllm/model", custom_outputs=policy, memoize=False), log_dir=log_dir, display="none")
