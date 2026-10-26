"""Inspect .eval logs -> game, opportunity, relay and guess tables (U5; KTD9, KTD12, E14).

Labels are recomputed from each game's raw record with the current relaygame.labels, so a
tracer fix relabels old logs. A game counts once: only samples with no error and a score
are kept, and when one game_id has several complete copies (a resumed batch), the copy from
the earliest log is used. With `require` hashes (main runs), games whose labels.py or prompts
hash differs are rejected and listed.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from inspect_ai.log import read_eval_log, read_eval_log_samples

from relaygame.task import game_metrics, is_scored

GAME_COLS = ["game_id", "tier", "condition", "mechanism", "monitor", "peer_log", "players", "A", "B", "L",
             "rounds", "steps", "paraphrase", "framing"]
# USD per million tokens (input, output), OpenRouter list prices read Oct 23 2026; local serving is free.
PRICES = {"qwen/qwen3-30b-a3b-instruct-2507": (0.09, 0.30), "qwen/qwen3.6-35b-a3b": (0.10, 0.95),
          "anthropic/claude-sonnet-5.5": (2.0, 10.0), "anthropic/claude-haiku-5.5": (0.10, 0.50)}


FREE_PREFIXES = ("openai-api/", "mockllm/", "none/")  # self-hosted or test models


def price(model: str) -> tuple[float, float]:
    """USD per million (input, output) tokens. Raises KeyError for a paid model missing from PRICES."""
    if model.startswith(FREE_PREFIXES):
        return 0.0, 0.0
    for k, p in PRICES.items():
        if model.endswith(k):
            return p
    raise KeyError(f"no price for {model}; add it to analysis/extract.py PRICES")


def cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    try:
        pin, pout = price(model)
    except KeyError:
        return float("nan")  # analysis reports unknown cost as missing, never as $0
    return (tokens_in * pin + tokens_out * pout) / 1e6


def log_files(paths) -> list[Path]:
    out = []
    for p in [paths] if isinstance(paths, (str, Path)) else paths:
        p = Path(p)
        out += sorted(p.rglob("*.eval")) if p.is_dir() else [p]
    return out


# Exploratory, post-hoc measure (runbook rule D, 2026-10-24): deal, threat and alliance language in LLM-sent
# messages, by keyword. Not validated against hand labels; reported as a keyword count only.
PACT_RE = re.compile(r"\b(won'?t|will not|not to|don'?t|do not) guess (you|me)\b|\bif you (don'?t|do not|won'?t) guess"
                     r"|\b(deal|trade|swap|exchange|alliance|truce|team up|work together|mutual)\b"
                     r"|\bor (else )?i('ll| will)\b|\bi('ll| will) (broadcast|reveal|expose|leak)\b|\bpromise\b", re.I)


def pact_counts(events: list[dict]) -> dict:
    llm = set(events[0]["llm"])
    texts = [m["text"] for e in events for m in e.get("messages") or []
             if isinstance(m, dict) and m.get("sender") in llm and m.get("text")]
    return {"llm_messages": len(texts), "pact_messages": sum(bool(PACT_RE.search(t)) for t in texts)}


def game_tables(events: list[dict], quiz: list, aware: list, meta: dict) -> dict[str, list[dict]]:
    """Rows for one game. `meta` holds the game columns (manifest row) plus anything to carry along."""
    metrics, t = game_metrics(events, quiz, aware)
    base = {k: meta.get(k) for k in GAME_COLS + ["model"]}
    llm = set(events[0]["llm"])
    return {
        "games": [{**meta, **metrics, **pact_counts(events)}],
        "opportunities": [{**base, **o, "relay_forms": ",".join(o["relay_forms"])} for o in t["opportunities"]],
        "relays": [{**base, "round": r["round"], "step": r["step"], "sender": r["sender"], "victim": r["victim"],
                    "form": r["form"], "source": r["source"], "sender_is_llm": r["sender"] in llm,
                    "provenance": r["provenance"], "n_recipients": len(r["recipients"]),
                    "n_novel": len(r["novel_recipients"]), "msg_ids": ",".join(r["msg_ids"])} for r in t["relays"]],
        "guesses": [{**base, **{k: v for k, v in g.items() if k not in ("forms", "carrier_senders")},
                     "forms": ",".join(g["forms"]), "carrier_senders": ",".join(g["carrier_senders"]),
                     "guesser_is_llm": g["guesser"] in llm} for g in t["guesses"]],
        "lies": [{**base, **x} for x in t["lies"]],
        "quiz": [{**base, **{k: q.get(k) for k in ("player", "pass1", "pass2")}} for q in quiz],
        "awareness": [{**base, **a} for a in aware],
    }


def complete_samples(paths, require: dict | None = None):
    """(kept {game_id: (header, file, sample)}, discarded, rejected, duplicates): one complete copy per game."""
    seen: dict[str, tuple] = {}
    discarded, rejected, duplicates = [], [], []
    headers = {f: read_eval_log(str(f), header_only=True) for f in log_files(paths)}
    for f in sorted(headers, key=lambda f: headers[f].eval.created):
        header = headers[f]
        for s in read_eval_log_samples(str(f), all_samples_required=False):
            gid = str(s.id)
            if not (is_scored(s) and s.store.get("events")):
                discarded.append({"game_id": gid, "log": f.name, "error": str(s.error)[:200] if s.error else "no score"})
                continue
            if require and any(s.metadata.get(k) != v for k, v in require.items()):
                rejected.append({"game_id": gid, "log": f.name,
                                 **{k: s.metadata.get(k) for k in require}})
                continue
            if gid in seen:
                duplicates.append({"game_id": gid, "log": f.name})
                continue
            s.events, s.messages, s.attachments = [], [], {}  # transcripts are unused downstream; bounds memory
            seen[gid] = (header, f, s)
    return seen, discarded, rejected, duplicates


def load(paths, require: dict | None = None) -> dict[str, pd.DataFrame]:
    """All tables from the logs under `paths`. Adds `rejected` (hash mismatch) and `discarded` (errored/partial)."""
    seen, discarded, rejected, duplicates = complete_samples(paths, require)
    tables: dict[str, list] = {}
    for header, f, s in seen.values():
        usage = s.model_usage or {}
        cost = sum(cost_usd(m, u.input_tokens, u.output_tokens) for m, u in usage.items())
        meta = {**{k: s.metadata.get(k) for k in GAME_COLS}, "model": header.eval.model,
                "seat_models": ",".join(sorted(set(s.store.get("seat_models", {}).values()))),
                "log": f.name, "working_min": (s.working_time or s.total_time or 0) / 60,
                "tokens_in": sum(u.input_tokens for u in usage.values()),
                "tokens_out": sum(u.output_tokens for u in usage.values()), "cost_usd": cost,
                "labels_sha256": s.metadata.get("labels_sha256"), "prompts_sha256": s.metadata.get("prompts_sha256")}
        for name, rows in game_tables(s.store["events"], s.store.get("quiz", []), s.store.get("awareness", []), meta).items():
            tables.setdefault(name, []).extend(rows)
    out = {k: pd.DataFrame(v) for k, v in tables.items()}
    for k in ("games", "opportunities", "relays", "guesses", "lies", "quiz", "awareness"):
        out.setdefault(k, pd.DataFrame())
    out["discarded"] = pd.DataFrame(discarded)
    out["rejected"] = pd.DataFrame(rejected)
    out["duplicates"] = pd.DataFrame(duplicates)
    for k in ("A", "B", "L", "players", "rounds", "steps"):
        for df in out.values():
            if k in df.columns:
                df[k] = pd.to_numeric(df[k])
    return out
