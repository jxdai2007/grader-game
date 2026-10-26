"""U9 decision rule (docs/pilot-relay-modes.md, amendment of 2026-10-23): player count, then two mechanism picks.

    uv run python analysis/pilot_decision.py logs/pilot

1. Player count: the all-LLM size (4 or 6, free and engine-dealt pooled) with more decided relay
   opportunities per minute of game runtime, unless its unparseable rate is at least 5 points higher.
2. All-LLM cross: free play if it reaches 0.5 opportunities per round at the chosen size, else engine-dealt.
3. Gain sweep: the scripted dealer if its cost per opportunity is lower than the cross mechanism's, else the cross mechanism.
"""

import sys

import pandas as pd

UNPARSEABLE_MARGIN = 0.05
FREE_MIN_OPP_PER_ROUND = 0.5


def arm_table(games: pd.DataFrame) -> pd.DataFrame:
    g = games.copy()
    g["arm"] = g["mechanism"] + "-" + g["players"].astype(int).astype(str)
    a = g.groupby(["arm", "mechanism", "players"]).agg(
        games=("game_id", "nunique"), rounds=("rounds", "sum"), opportunities=("opportunities", "sum"),
        relayed=("relayed", "sum"), indeterminate=("indeterminate", "sum"), leaks=("leaks", "sum"),
        unparseable=("unparseable", "sum"), timeout=("timeout", "sum"), turns=("turns", "sum"),
        minutes=("working_min", "sum"), cost_usd=("cost_usd", "sum")).reset_index()
    a["opp_per_round"] = a["opportunities"] / a["rounds"]
    a["opp_per_min"] = a["opportunities"] / a["minutes"]
    a["unparseable_rate"] = a["unparseable"] / a["turns"]
    a["cost_per_opp"] = a["cost_usd"] / a["opportunities"].where(a["opportunities"] > 0)
    a["relay_rate"] = a["relayed"] / a["opportunities"].where(a["opportunities"] > 0)
    return a


def decide(a: pd.DataFrame) -> dict:
    llm = a[a["mechanism"].isin(["free", "seeded"])]
    size = llm.groupby("players")[["opportunities", "minutes", "unparseable", "turns"]].sum()
    size["opp_per_min"] = size["opportunities"] / size["minutes"]
    size["unparseable_rate"] = size["unparseable"] / size["turns"]
    best, other = size["opp_per_min"].idxmax(), size["opp_per_min"].idxmin()
    if best != other and size.loc[best, "unparseable_rate"] - size.loc[other, "unparseable_rate"] >= UNPARSEABLE_MARGIN:
        best = other
    players = int(best)
    at = llm[llm["players"] == players].set_index("mechanism")
    free_ok = "free" in at.index and at.loc["free", "opp_per_round"] >= FREE_MIN_OPP_PER_ROUND
    cross = "free" if free_ok else "seeded"
    dealer = a[a["mechanism"] == "dealer"]
    dealer_cost = dealer["cost_per_opp"].iloc[0] if len(dealer) else float("nan")
    sweep = "dealer" if dealer_cost < at.loc[cross, "cost_per_opp"] else cross
    return {"players": players, "cross_mechanism": cross, "sweep_mechanism": sweep,
            "size_table": size.reset_index().to_dict("records")}


def main(paths) -> int:
    from analysis.extract import load

    t = load(paths)
    a = arm_table(t["games"])
    pd.set_option("display.width", 200)
    print(a.drop(columns=["arm"]).round(4).to_string(index=False))
    d = decide(a)
    print(f"selected players={d['players']} cross_mechanism={d['cross_mechanism']} sweep_mechanism={d['sweep_mechanism']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["logs/pilot"]))
