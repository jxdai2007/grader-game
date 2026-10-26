"""Exploratory, post-hoc (2026-10-24): deterrence vs removal under the announced monitor (run 1).

    uv run python analysis/first_chance.py   # reads results/main/opportunities.csv, writes results/main/first_chance.csv

The announced monitor removes a player after a detected relay, so later rounds hold only players who had not relayed.
Rates on each holder's first opportunity, and in round 1, come before any removal can act.
"""

import pandas as pd

from analysis import stats

o = pd.read_csv("results/main/opportunities.csv")
o["model"] = o["model"].astype(str).str.split("/").str[-1]
d = stats.opp_frame(o)
rows = []
for (model, mech, framing, B, cond), g in d.groupby(["model", "mechanism", "framing", "B", "condition"]):
    if framing != "standard" or B != 10:
        continue
    first = g.sort_values(["round"]).groupby(["game_id", "holder"]).head(1)
    r1 = g[g["round"] == g["round"].min()]
    row = {"model": model, "mechanism": mech, "condition": cond, "games": g["game_id"].nunique(),
           "opportunities": len(g), "relay_rate_all": g["relayed"].mean(),
           "holder_first_n": len(first), "relay_rate_holder_first": first["relayed"].mean(),
           "round1_n": len(r1), "relay_rate_round1": r1["relayed"].mean()}
    for name, sub in (("all", g), ("holder_first", first)):
        est, lo, hi = stats.ratio_ci(sub, "relayed", "one")
        row.update({f"{name}_lo": lo, f"{name}_hi": hi})
    rows.append(row)
out = pd.DataFrame(rows)
out.to_csv("results/main/first_chance.csv", index=False)
print(out.round(3).to_string(index=False))
