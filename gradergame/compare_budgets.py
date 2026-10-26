"""Pilot: the same 12 games (same seeds) at a 1k and a 4k thinking budget, side by side (Jollen's 09:00 decision).

    uv run python -m gradergame.compare_budgets results/grader_pilot_b1k results/grader_pilot_b4k
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

KEYS = ["reciprocal_rounds", "co_inflation_rounds", "co_papers_inflated", "out_papers_deflated", "out_papers_inflated",
        "pair_rounds", "co_papers", "out_papers", "caught", "unmarked", "unparseable", "timeout", "deal_messages",
        "messages", "private_messages", "quiz_fail", "awareness_flag", "working_min"]


def load(d: str, tag: str) -> pd.DataFrame:
    g = pd.read_csv(Path(d) / "games.csv")
    g["cell"] = g["condition"]
    g["rep"] = g["game_id"].str[-3:]
    return g.set_index(["cell", "rep"])[KEYS].add_suffix(f"_{tag}")


def main(a: str, b: str) -> pd.DataFrame:
    x, y = load(a, "1k"), load(b, "4k")
    j = x.join(y, how="outer")
    rows = []
    for cell, d in j.groupby(level=0):
        r = {"cell": cell, "games_1k": d["pair_rounds_1k"].notna().sum(), "games_4k": d["pair_rounds_4k"].notna().sum()}
        for t in ("1k", "4k"):
            pr = d[f"pair_rounds_{t}"].sum()
            r[f"reciprocal_{t}"] = d[f"reciprocal_rounds_{t}"].sum() / pr if pr else float("nan")
            r[f"co_inflation_{t}"] = d[f"co_inflation_rounds_{t}"].sum() / pr if pr else float("nan")
            op = d[f"out_papers_{t}"].sum()
            r[f"out_deflated_{t}"] = d[f"out_papers_deflated_{t}"].sum() / op if op else float("nan")
            r[f"out_inflated_{t}"] = d[f"out_papers_inflated_{t}"].sum() / op if op else float("nan")
            r[f"unparseable_{t}"] = d[f"unparseable_{t}"].sum()
            r[f"min_per_game_{t}"] = d[f"working_min_{t}"].mean()
        rows.append(r)
    out = pd.DataFrame(rows)
    print(out.round(2).to_string(index=False))
    return out


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
