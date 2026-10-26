"""Regenerate every table and figure from Inspect logs (U5, U12). Every reported number comes from here.

    uv run python analysis/run_all.py                          # main runs: logs/main, hashes from docs/preregistration.md
    uv run python analysis/run_all.py logs/pilot --out results/pilot --no-hash-check
"""

import argparse
import re
from pathlib import Path

import pandas as pd

from analysis import figures, stats
from analysis.extract import load

ROOT = Path(__file__).resolve().parent.parent


def prereg_hashes(path: Path = ROOT / "docs" / "preregistration.md") -> dict:
    text = path.read_text()
    found = dict(re.findall(r"(labels_sha256|prompts_sha256):\s*`?([0-9a-f]{64})", text))
    assert len(found) == 2, f"{path} must record labels_sha256 and prompts_sha256"
    return found


def md(df: pd.DataFrame) -> str:
    return "```\n" + df.round(4).to_string(index=False) + "\n```" if len(df) else "(empty)"


def run(paths, out: Path, require=None) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    t = load(paths, require=require)
    games, opps, guesses = t["games"], t["opportunities"], t["guesses"]
    report = [f"# Results from {', '.join(map(str, paths))}", "",
              f"games={len(games)} discarded={len(t['discarded'])} rejected={len(t['rejected'])} "
              f"duplicates={len(t['duplicates'])}", ""]
    for name in ("games", "opportunities", "relays", "guesses", "lies", "quiz", "awareness", "discarded", "rejected"):
        t[name].to_csv(out / f"{name}.csv", index=False)
    if len(games) == 0:
        (out / "results.md").write_text("\n".join(report + ["no complete games"]))
        return t
    for df in (games, opps, guesses):
        if "model" in df:
            df["model"] = df["model"].fillna("").astype(str).str.split("/").str[-1]
    # An arm is one model, mechanism, size, framing and payoff scale: the instructed control, the x10 scale cell and
    # each model are never pooled with the gain curves.
    arm = ["model", "mechanism", "players", "framing", "B"]
    tables = {}
    if len(opps):
        tables["rates_by_cell"] = stats.rate_table(opps, guesses, arm + ["condition", "A"])
        tables["rates_by_condition"] = stats.rate_table(opps, guesses, arm + ["condition"])
        tables["rates_by_paraphrase"] = stats.rate_table(opps, guesses, arm + ["condition", "paraphrase"])
        if games["awareness_flag"].any():
            clean = set(games.loc[games["awareness_flag"] == 0, "game_id"])
            tables["rates_by_condition_unflagged"] = stats.rate_table(
                opps[opps["game_id"].isin(clean)], guesses[guesses["game_id"].isin(clean)], arm + ["condition"])
        fits, held = [], []
        for key, oa in opps.groupby(arm):
            if oa["A"].nunique() < 2:
                continue
            tag = dict(zip(arm, key))
            slug = re.sub(r"[^A-Za-z0-9.]+", "-", "_".join(map(str, key)))
            c = figures.relay_curves(oa, str(out / f"relay_curves_{slug}.png"),
                                     title=f"Relay rate over gain A: {tag['model']} {tag['mechanism']}{tag['players']}")
            fits += [{**tag, **r} for r in c.to_dict("records")]
            for cond, dc in stats.opp_frame(oa).groupby("condition"):
                if dc["A"].nunique() >= 2 and dc["game_id"].nunique() >= 5:
                    held.append({**tag, "condition": cond, **stats.heldout_check(dc)})
        if fits:
            tables["curve_fits"] = pd.DataFrame(fits)
            tables["heldout_check"] = pd.DataFrame(held)
        bars = tables["rates_by_condition"].assign(
            cell=lambda t: t[arm + ["condition"]].astype(str).agg(" ".join, axis=1))
        figures.rate_bars(bars, str(out / "relay_rate_by_condition.png"), label="cell")
    tables["game_measures_by_condition"] = stats.game_measures(games, arm + ["condition"])
    pacts = []  # exploratory keyword measure (extract.PACT_RE), share of LLM messages
    for key, d in games.assign(one=1).groupby(arm + ["condition"]):
        r = stats.ratio_ci(d, "pact_messages", "llm_messages")
        pacts.append({**dict(zip(arm + ["condition"], key)), "games": d["game_id"].nunique(),
                      "llm_messages": int(d["llm_messages"].sum()), "pact_share": r[0], "pact_lo": r[1], "pact_hi": r[2]})
    tables["pact_language_exploratory"] = pd.DataFrame(pacts)
    tables["references"] = pd.DataFrame([{"monitor": m, **stats.references(m)} for m in ("off", "logged", "announced")])
    tables["run_summary"] = games.groupby(arm + ["condition"]).agg(
        games=("game_id", "nunique"), turns=("turns", "sum"), unparseable=("unparseable", "sum"),
        timeout=("timeout", "sum"), lies=("lies", "sum"), awareness_flags=("awareness_flag", "sum"),
        quiz_fail=("quiz_fail", "sum"), cost_usd=("cost_usd", "sum"), minutes=("working_min", "sum")).reset_index()
    for name, df in tables.items():
        df.to_csv(out / f"{name}.csv", index=False)
        report += [f"## {name}", "", md(df), ""]
    (out / "results.md").write_text("\n".join(report))
    print(f"wrote {len(tables)} tables and figures to {out}")
    return t


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", default=["logs/main"])
    ap.add_argument("--out", default="results/main")
    ap.add_argument("--no-hash-check", action="store_true")
    a = ap.parse_args()
    require = None if a.no_hash_check else prereg_hashes()
    run(a.paths, Path(a.out), require)
