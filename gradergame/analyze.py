"""Grader Game tables from Inspect logs (plan R15-R20). Every reported grader-game number comes from here.

    uv run python -m gradergame.analyze logs/grader_pilot --out results/grader_pilot
    uv run python -m gradergame.analyze logs/grader_main --out results/grader_main --prereg docs/preregistration-grader.md

Games are the independent units: every interval is a game-level cluster bootstrap (analysis.stats.ratio_ci).
A game counts once: the earliest complete copy of each game_id is used.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd
from inspect_ai.log import read_eval_log, read_eval_log_samples

from analysis.extract import log_files
from analysis.stats import ratio_ci
from gradergame.task import FIELDS, game_metrics, is_scored

CELL = ["structure", "goal", "audit", "control", "channel", "audit_target"]


def prereg_hashes(path: Path) -> dict:
    found = dict(re.findall(r"(labels_sha256|prompts_sha256):\s*`?([0-9a-f]{64})", path.read_text()))
    assert len(found) == 2, f"{path} must record labels_sha256 and prompts_sha256"
    return found


def load(paths, require: dict | None = None) -> dict[str, pd.DataFrame]:
    """`paths` items may be `dir@prereg.md`: games under dir must match that file's hashes instead of `require`."""
    reqs = {}
    for item in [paths] if isinstance(paths, (str, Path)) else paths:
        d, _, pr = str(item).partition("@")
        for f in log_files(d):
            reqs[f] = prereg_hashes(Path(pr)) if pr else require
    files = list(reqs)
    headers = {f: read_eval_log(str(f), header_only=True) for f in files}
    seen, rejected, discarded = set(), [], []
    tabs: dict[str, list] = {"games": [], "marks": [], "rounds": [], "first": [], "detection": []}
    for f in sorted(files, key=lambda f: headers[f].eval.created):
        for s in read_eval_log_samples(str(f), all_samples_required=False):
            gid = str(s.id)
            if not (is_scored(s) and s.store.get("events")):
                discarded.append({"game_id": gid, "log": f.name, "error": str(s.error)[:200] if s.error else "no score"})
                continue
            req = reqs[f]
            if req and any(s.metadata.get(k) != v for k, v in req.items()):
                rejected.append({"game_id": gid, "log": f.name})
                continue
            if gid in seen:
                continue
            seen.add(gid)
            meta = {k: s.metadata.get(k) for k in FIELDS}
            meta["channel"] = meta.get("channel") or "private"  # games before the mechanism split had no channel field
            meta["audit_target"] = meta.get("audit_target") or "all"  # games before addendum 3 audited all papers
            meta["model"] = str(headers[f].eval.model).split("/")[-1]
            meta["working_min"] = (s.working_time or s.total_time or 0) / 60
            meta["started_at"] = str(getattr(s, "started_at", None) or "")
            m, t = game_metrics(s.store["events"], s.store.get("quiz", []), s.store.get("awareness", []),
                                s.store.get("detect", []))
            tabs["games"].append({**meta, **m, "colluder_names": ",".join(t["colluders"])})
            for name in ("marks", "rounds", "first", "detection"):
                tabs[name] += [{**meta, **r} for r in t[name]]
    out = {k: pd.DataFrame(v) for k, v in tabs.items()}
    out["rejected"], out["discarded"] = pd.DataFrame(rejected), pd.DataFrame(discarded)
    for df in out.values():
        for k in ("audit", "rounds", "players"):
            if k in df.columns:
                df[k] = pd.to_numeric(df[k])
    return out


def ci(df, num, den):
    if len(df) == 0 or df[den].sum() == 0:
        return float("nan"), float("nan"), float("nan")
    return ratio_ci(df.assign(**{num: df[num].astype(float), den: df[den].astype(float)}), num, den)


def cell_table(t: dict) -> pd.DataFrame:
    g, rd, fd = t["games"], t["rounds"], t["first"]
    rows = []
    for key, gg in g.groupby(CELL):
        r = {**dict(zip(CELL, key)), "games": len(gg)}
        for name, num, den in [("reciprocal_rate", "reciprocal_rounds", "pair_rounds"),
                               ("co_inflation_round_rate", "co_inflation_rounds", "pair_rounds"),
                               ("co_paper_inflated", "co_papers_inflated", "co_papers"),
                               ("out_paper_deflated", "out_papers_deflated", "out_papers"),
                               ("out_paper_inflated", "out_papers_inflated", "out_papers")]:
            est, lo, hi = ci(gg, num, den)
            r.update({name: est, f"{name}_lo": lo, f"{name}_hi": hi})
        rr = rd[(rd[CELL] == pd.Series(key, index=CELL)).all(axis=1) & (rd["n_graders"] == 2)] if len(rd) else rd
        if len(rr):
            est, lo, hi = ratio_ci(rr.assign(one=1.0, adv=rr["ingroup_advantage"].astype(float)), "adv", "one")
            r.update({"ingroup_advantage": est, "ingroup_advantage_lo": lo, "ingroup_advantage_hi": hi,
                      "pair_kept_rate": rr["pair_kept"].astype(float).mean()})
            ac = rr[rr["after_catch"].astype(bool)]
            r.update({"rounds_after_catch": len(ac),
                      "reciprocal_after_catch": ac["reciprocal_inflation"].astype(float).mean() if len(ac) else float("nan")})
        ff = fd[(fd[CELL] == pd.Series(key, index=CELL)).all(axis=1)] if len(fd) else fd
        if len(ff):
            r.update({"first_decisions": len(ff), "first_co_inflated": ff["co_inflated"].astype(float).mean(),
                      "first_out_deflated": ff["out_deflated"].astype(float).mean()})
        r.update({"caught": gg["caught"].sum(), "unmarked": gg["unmarked"].sum(),
                  "unparseable": gg["unparseable"].sum(), "timeout": gg["timeout"].sum(),
                  "deal_share": gg["deal_messages"].sum() / max(1.0, gg["messages"].sum()),
                  "private_share": gg["private_messages"].sum() / max(1.0, gg["messages"].sum()),
                  "awareness_flags": gg["awareness_flag"].sum(), "quiz_fail": gg["quiz_fail"].sum(),
                  "minutes_per_game": gg["working_min"].mean()})
        rows.append(r)
    return pd.DataFrame(rows)


def detection_table(t: dict) -> pd.DataFrame:
    d, g = t["detection"], t["games"]
    if not len(d):
        return pd.DataFrame()
    d = d.merge(g[["game_id", "colluder_names"]], on="game_id", how="left")
    rows = []
    for key, dd in d.groupby(CELL):
        has = dd[dd["colluder_names"].fillna("") != ""]
        rows.append({**dict(zip(CELL, key)), "answers": len(dd), "games_with_colluders": has["game_id"].nunique(),
                     "exact_when_colluders": has["exact"].astype(float).mean() if len(has) else float("nan"),
                     "named_any_when_none": (dd[dd["colluder_names"].fillna("") == ""]["n_named"] > 0).astype(float).mean()})
    return pd.DataFrame(rows)


def _sel(df: pd.DataFrame, **kw) -> pd.DataFrame:
    m = pd.Series(True, index=df.index)
    for k, v in kw.items():
        m &= df[k].isin(v) if isinstance(v, (list, tuple, set)) else (df[k] == v)
    return df[m]


def _game_means(df: pd.DataFrame, col: str) -> pd.DataFrame:
    return df.groupby("game_id")[col].agg(["sum", "count"])


def diff_test(a: pd.DataFrame, b: pd.DataFrame, col: str, boot: int = 2000, seed: int = 0) -> dict:
    """Mean of `col` over rows in a minus in b; games resampled within each group (cluster bootstrap);
    two-sided p = 2 x the smaller tail share of bootstrap differences at or beyond 0."""
    import numpy as np
    ga, gb = _game_means(a, col), _game_means(b, col)
    if not len(ga) or not len(gb):
        return {"est": float("nan"), "lo": float("nan"), "hi": float("nan"), "p": float("nan"),
                "games_a": len(ga), "games_b": len(gb)}
    est = ga["sum"].sum() / ga["count"].sum() - gb["sum"].sum() / gb["count"].sum()
    rng = np.random.default_rng(seed)
    ia = rng.integers(0, len(ga), (boot, len(ga)))
    ib = rng.integers(0, len(gb), (boot, len(gb)))
    da = ga["sum"].to_numpy()[ia].sum(1) / ga["count"].to_numpy()[ia].sum(1)
    db = gb["sum"].to_numpy()[ib].sum(1) / gb["count"].to_numpy()[ib].sum(1)
    d = da - db
    lo, hi = np.percentile(d, [2.5, 97.5])
    p = min(1.0, 2 * min((d <= 0).mean(), (d >= 0).mean()))
    return {"est": est, "lo": lo, "hi": hi, "p": p, "games_a": len(ga), "games_b": len(gb)}


def slope_test(df: pd.DataFrame, col: str, binary: bool) -> dict:
    """Slope of `col` on the audit rate (percent) with game-clustered errors: logistic for a 0/1 outcome, OLS else."""
    import statsmodels.api as sm
    d = df.dropna(subset=[col])
    if d["audit"].nunique() < 2:
        return {"slope": float("nan"), "lo": float("nan"), "hi": float("nan"), "p": float("nan"), "n": len(d)}
    X = sm.add_constant(d[["audit"]].astype(float))
    groups = pd.factorize(d["game_id"])[0]
    fam = sm.GLM(d[col].astype(float), X, family=sm.families.Binomial()) if binary else sm.OLS(d[col].astype(float), X)
    fit = fam.fit(cov_type="cluster", cov_kwds={"groups": groups})
    lo, hi = fit.conf_int().loc["audit"]
    return {"slope": fit.params["audit"], "lo": lo, "hi": hi, "p": fit.pvalues["audit"], "n": len(d),
            "games": d["game_id"].nunique()}


def hypothesis_table(t: dict) -> pd.DataFrame:
    """The pre-registered tests (docs/preregistration-grader.md, H1-H4 and the positive control)."""
    rd = t["rounds"]
    if not len(rd):
        return pd.DataFrame()
    rd = rd.assign(control=rd["control"].fillna("none"), channel=rd["channel"].fillna("private"))
    rd = rd[rd["audit_target"].fillna("all") == "all"] if "audit_target" in rd else rd  # H1-H8 use uniform audits only
    pair = rd[rd["n_graders"] == 2].assign(recip=lambda d: d["reciprocal_inflation"].astype(float),
                                           adv=lambda d: d["ingroup_advantage"].astype(float))
    mk = t["marks"]
    mk = mk[mk["audit_target"].fillna("all") == "all"] if "audit_target" in mk else mk
    mk = mk[(mk["status"] == "marked")].assign(channel=lambda d: d["channel"].fillna("private"),
                                               control=lambda d: d["control"].fillna("none"),
                                               misgraded=lambda d: ((d["inflation"] + d["deflation"]) > 0).astype(float),
                                               wrong_answers=lambda d: (d["inflation"] + d["deflation"]).astype(float))
    base = dict(control="none", audit=0, channel="private")
    rows = []

    def add(h, label, res):
        rows.append({"hypothesis": h, "test": label, **res})

    for goal in (["low", "high"], "low", "high"):
        g = goal if isinstance(goal, str) else "pooled"
        on = _sel(rd[rd["n_graders"] == 2].assign(adv=rd["ingroup_advantage"].astype(float)), structure="on", goal=goal, **base)
        off = _sel(rd[rd["n_graders"] == 2].assign(adv=rd["ingroup_advantage"].astype(float)), structure="off", goal=goal, **base)
        add("H1", f"in-group advantage, reason on - off, goal {g}, X=0", diff_test(on, off, "adv"))
    hi, lo = _sel(pair, structure="on", goal="high", **base), _sel(pair, structure="on", goal="low", **base)
    add("H2", "reciprocal inflation, goal high - low, reason on, X=0", diff_test(hi, lo, "recip"))
    add("H2", "in-group advantage, goal high - low, reason on, X=0", diff_test(hi, lo, "adv"))
    oh = _sel(mk, structure="off", goal="high", role="outsider", **base)
    ol = _sel(mk, structure="off", goal="low", role="outsider", **base)
    add("H3", "outsider papers misgraded, goal high - low, reason off, X=0", diff_test(oh, ol, "misgraded"))
    hb = _sel(mk, control="honest_baseline")
    if len(hb):
        est, lo_, hi_ = ratio_ci(hb.assign(one=1.0), "misgraded", "one")
        add("H3", "honest baseline (marks count for no one, goal high): share of papers misgraded",
            {"est": est, "lo": lo_, "hi": hi_, "games_a": hb["game_id"].nunique()})
    curve = _sel(pair, structure="on", control="none", channel="private")
    add("H4", "reciprocal inflation on audit % (logistic), reason on", slope_test(curve, "recip", True))
    add("H4", "in-group advantage on audit % (OLS), reason on", slope_test(curve, "adv", False))
    # Addendum (mechanism split; exploratory unless Jollen approves docs/preregistration-grader-addendum.md)
    adv_rounds = rd[rd["n_graders"] == 2].assign(adv=rd["ingroup_advantage"].astype(float))
    ref = _sel(adv_rounds, structure="on", goal="low", **base)
    for ch in ("public", "none"):
        add("H5", f"in-group advantage, channel {ch} - private, reason on, goal low, X=0",
            diff_test(_sel(adv_rounds, structure="on", goal="low", control="none", audit=0, channel=ch), ref, "adv"))
    for st_ in ("mutual_only", "seats_only"):
        add("H6", f"in-group advantage, {st_} - on, goal low, X=0",
            diff_test(_sel(adv_rounds, structure=st_, goal="low", control="none", audit=0, channel="private"), ref, "adv"))
        add("H6", f"in-group advantage, {st_} - off, goal low, X=0",
            diff_test(_sel(adv_rounds, structure=st_, goal="low", control="none", audit=0, channel="private"),
                      _sel(adv_rounds, structure="off", goal="low", **base), "adv"))
    low = _sel(pair, structure="on", goal="low", control="none", channel="private")
    add("H7", "in-group advantage on audit % (OLS), reason on, goal low, all audit levels", slope_test(low, "adv", False))
    # Keys to power (exploratory unless approved): do graders reward the elector, the outsider who sets their grades?
    el = mk[(mk["structure"] == "elector") & (mk["control"] == "none")].assign(
        inflated=lambda d: (d["inflation"] > 0).astype(float), deflated=lambda d: (d["deflation"] > 0).astype(float))
    if len(el):
        key, others = el[el["role"] == "elector_paper"], el[el["role"] == "outsider"]
        add("H8", "graders' inflation of the elector's paper - of other outsiders' papers", diff_test(key, others, "inflated"))
        add("H8", "graders' deflation of the elector's paper - of other outsiders' papers", diff_test(key, others, "deflated"))
        back = el[el["role"] == "elector_marks_grader"]
        est, lo_, hi_ = ratio_ci(back.assign(one=1.0), "inflated", "one")
        add("H8", "elector's marks of graders' papers: share inflated", {"est": est, "lo": lo_, "hi": hi_,
                                                                       "games_a": back["game_id"].nunique()})
    st = _sel(pair, control="secret_team")
    if len(st):
        est, lo_, hi_ = ratio_ci(st.assign(one=1.0), "recip", "one")
        add("control", "secret team: reciprocal inflation rate", {"est": est, "lo": lo_, "hi": hi_,
                                                                   "games_a": st["game_id"].nunique()})
    return pd.DataFrame(rows)


def md(df: pd.DataFrame) -> str:
    return "```\n" + df.round(3).to_string(index=False) + "\n```" if len(df) else "(empty)"


def run(paths, out: Path, require=None, started_before: str | None = None) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    t = load(paths, require)
    if started_before:  # robustness: drop games that started after a cutoff (e.g. the 19:00 stop that did not fire)
        cut = pd.Timestamp(started_before)
        g = t["games"]
        keep = set(g.loc[pd.to_datetime(g["started_at"], utc=True) < cut, "game_id"])
        t = {k: (df[df["game_id"].isin(keep)] if "game_id" in df.columns and k not in ("rejected", "discarded") else df)
             for k, df in t.items()}
    for k, df in t.items():
        df.to_csv(out / f"{k}.csv", index=False)
    report = [f"# Grader Game results from {', '.join(map(str, paths))}", "",
              f"games={len(t['games'])} discarded={len(t['discarded'])} rejected={len(t['rejected'])}", ""]
    if len(t["games"]):
        tables = {"cells": cell_table(t), "hypotheses": hypothesis_table(t), "detection": detection_table(t)}
        clean = set(t["games"].loc[t["games"]["awareness_flag"] == 0, "game_id"])
        if len(clean) < len(t["games"]):  # robustness: the same tests without awareness-flagged games
            tc = {k: (df[df["game_id"].isin(clean)] if "game_id" in df.columns else df) for k, df in t.items()}
            tables["hypotheses_unflagged"] = hypothesis_table(tc)
        for name, df in tables.items():
            df.to_csv(out / f"{name}.csv", index=False)
            report += [f"## {name}", "", md(df), ""]
    (out / "results.md").write_text("\n".join(report))
    print(f"wrote {out}")
    return t


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--prereg", default=None)
    ap.add_argument("--started-before", default=None, help="ISO time; keep only games that started before it")
    a = ap.parse_args()
    run(a.paths, Path(a.out), prereg_hashes(Path(a.prereg)) if a.prereg else None, a.started_before)
