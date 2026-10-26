"""Addendum 3: predict the targeted-audit cells from the uniform-audit cells, then score the predictions.

    uv run python -m gradergame.predict_target predict results/grader_all  # writes docs/predictions-target.csv
    uv run python -m gradergame.predict_target score results/grader_target # scores the new games against it

Two acts per two-grader round: a grader inflating its co-grader's paper (1 paper) and a grader deflating an outsider's
paper (4 papers). Rates are shares of papers (marked papers only), as in Table 1.

- Act-specific prediction (zero free parameters, read from the measured uniform-audit curve): each act responds only
  to the audit risk on the papers that act touches. In the cell where only the graders' papers can be re-marked at
  25%, co-grader inflation equals the uniform 25% cell and outsider deflation equals the uniform 0% cell; in the
  outsiders-only cell it is the other way round.
- Full general-deterrence pole (the baseline): both acts respond to the overall share of a grader's marked papers that
  can be re-marked: 1 of 5 papers at 25% = 5% (graders-only), 4 of 5 at 25% = 20% (outsiders-only).
Source cells: reason on, goal push low, private messages, no control (the targeted cells use the same settings).

Prediction intervals for a new cell of n games: the source cell's rate is resampled by game (cluster bootstrap), then
n new games are drawn with between-game spread from a beta-binomial whose intraclass correlation is estimated from all
uniform cells for that act. The predictions file holds n = 4; a cell that ends with fewer games is scored against
intervals recomputed by the same code for its actual n.
"""

from __future__ import annotations

import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("docs/predictions-target.csv")
ACTS = {"co_inflated": ("co_grader", "inflation", 6), "out_deflated": ("outsider", "deflation", 24)}  # papers per game
MODEL = {("graders", "co_inflated"): 25, ("graders", "out_deflated"): 0,
         ("outsiders", "co_inflated"): 0, ("outsiders", "out_deflated"): 25}
BASELINE = {"graders": 5, "outsiders": 20}
# the two rates where the prediction and the general-deterrence pole disagree (the unaudited act in each cell)
DISCRIMINATING = {"D1": ("graders", "out_deflated"), "D2": ("outsiders", "co_inflated")}
N_GAMES, DRAWS, SEED, MIN_GAMES = 4, 20000, 0, 3


def papers(res_dir: str) -> pd.DataFrame:
    mk = pd.read_csv(Path(res_dir) / "marks.csv")
    mk = mk.assign(control=mk["control"].fillna("none"), channel=mk["channel"].fillna("private"),
                   audit_target=mk["audit_target"].fillna("all") if "audit_target" in mk else "all")
    mk = mk[(mk["status"] == "marked") & mk["pair_round"].astype(bool) & (mk["structure"] == "on")
            & (mk["control"] == "none") & (mk["channel"] == "private") & (mk["goal"] == "low")]
    return mk


def act_rows(mk: pd.DataFrame, act: str) -> pd.DataFrame:
    role, col, _ = ACTS[act]
    d = mk[mk["role"] == role]
    return d.assign(y=(d[col] > 0).astype(float))


def icc(d: pd.DataFrame) -> float:
    """Method-of-moments intraclass correlation of the 0/1 outcome across games, pooled over cells."""
    vals = []
    for _, c in d.groupby(["audit", "audit_target"]):
        g = c.groupby("game_id")["y"].agg(["mean", "count"])
        if len(g) < 2:
            continue
        p, nbar = c["y"].mean(), g["count"].mean()
        if 0 < p < 1:
            between = g["mean"].var(ddof=1)
            vals.append(max(0.0, (between - p * (1 - p) / nbar) / (p * (1 - p) * (1 - 1 / nbar))))
    return float(np.clip(np.mean(vals) if vals else 0.1, 0.01, 0.9))


def predictive(src: pd.DataFrame, rho: float, n_per_game: int, rng, n_games: int) -> np.ndarray:
    games = src.groupby("game_id")["y"].agg(["sum", "count"]).to_numpy()
    out = np.empty(DRAWS)
    for i in range(DRAWS):
        b = games[rng.integers(0, len(games), len(games))]
        mu = np.clip(b[:, 0].sum() / b[:, 1].sum(), 1e-4, 1 - 1e-4)
        k = (1 / rho) - 1
        pg = rng.beta(mu * k, (1 - mu) * k, n_games)
        out[i] = rng.binomial(n_per_game, pg).sum() / (n_per_game * n_games)
    return out


def predict(res_dir: str, n_games: dict | None = None) -> pd.DataFrame:
    """n_games: {target: games in that cell}; default 4 for both."""
    mk = papers(res_dir)
    mk = mk[mk["audit_target"] == "all"]
    rng = np.random.default_rng(SEED)
    rows = []
    for (target, act), x in MODEL.items():
        d = act_rows(mk, act)
        rho = icc(d)
        n = (n_games or {}).get(target, N_GAMES)
        for kind, audit in (("model", x), ("baseline", BASELINE[target])):
            src = d[d["audit"] == audit]
            draws = predictive(src, rho, ACTS[act][2], rng, n)
            rows.append({"cell": f"X25-{target}", "act": act, "predictor": kind, "source_audit": audit,
                         "source_games": src["game_id"].nunique(), "point": src["y"].mean(),
                         "lo95": float(np.quantile(draws, 0.025)), "hi95": float(np.quantile(draws, 0.975)),
                         "icc": rho, "n_games": n})
    return pd.DataFrame(rows)


def cell_games(mk: pd.DataFrame, target: str, act: str) -> np.ndarray:
    d = act_rows(mk[(mk["audit"] == 25) & (mk["audit_target"] == target)], act)
    return d.groupby("game_id")["y"].agg(["sum", "count"]).to_numpy()


def perm_test(a: np.ndarray, b: np.ndarray) -> dict:
    """Exact two-sided permutation test of the pooled-rate difference a - b over all splits of the games."""
    est = a[:, 0].sum() / a[:, 1].sum() - b[:, 0].sum() / b[:, 1].sum()
    allg = np.vstack([a, b])
    stats = []
    for idx in combinations(range(len(allg)), len(a)):
        m = np.zeros(len(allg), bool)
        m[list(idx)] = True
        x, y = allg[m], allg[~m]
        stats.append(x[:, 0].sum() / x[:, 1].sum() - y[:, 0].sum() / y[:, 1].sum())
    stats = np.array(stats)
    p = float((np.abs(stats) >= abs(est) - 1e-12).mean())
    return {"est": est, "p": p, "games_a": len(a), "games_b": len(b), "min_p": 2 / len(stats)}


def spillover(mk: pd.DataFrame, uni: pd.DataFrame, target: str, act: str, boot: int = 2000) -> dict:
    """lambda = (uniform-0% rate - observed) / (uniform-0% rate - uniform-25% rate): 0 = no spillover of deterrence
    to the unaudited act (the prediction), 1 = as deterred as under a uniform 25% audit."""
    rng = np.random.default_rng(SEED)
    obs = cell_games(mk, target, act)
    u = act_rows(uni, act)
    g0 = u[u["audit"] == 0].groupby("game_id")["y"].agg(["sum", "count"]).to_numpy()
    g25 = u[u["audit"] == 25].groupby("game_id")["y"].agg(["sum", "count"]).to_numpy()
    rate = lambda g: g[:, 0].sum() / g[:, 1].sum()  # noqa: E731
    lam = lambda o, z, t: (rate(z) - rate(o)) / (rate(z) - rate(t)) if rate(z) != rate(t) else np.nan  # noqa: E731
    draws = [lam(obs[rng.integers(0, len(obs), len(obs))], g0[rng.integers(0, len(g0), len(g0))],
                 g25[rng.integers(0, len(g25), len(g25))]) for _ in range(boot)]
    draws = np.array([d for d in draws if np.isfinite(d)])
    return {"lambda": lam(obs, g0, g25), "lo": float(np.quantile(draws, 0.025)) if len(draws) else np.nan,
            "hi": float(np.quantile(draws, 0.975)) if len(draws) else np.nan}


def endgame(mk: pd.DataFrame, target: str) -> dict:
    """H10: outsider deflation in round 4 minus rounds 2-3, per game; exact two-sided sign-flip test over games."""
    d = act_rows(mk[(mk["audit"] == 25) & (mk["audit_target"] == target)], "out_deflated")
    g = d.assign(late=d["round"] == d["round"].max()).groupby(["game_id", "late"])["y"].mean().unstack().dropna()
    diff = (g.get(True, pd.Series(dtype=float)) - g.get(False, pd.Series(dtype=float))).to_numpy()
    if not len(diff):
        return {"mean_diff": np.nan, "p": np.nan, "games": 0, "up": 0, "down": 0}
    signs = np.array(np.meshgrid(*[[1, -1]] * len(diff))).reshape(len(diff), -1).T
    null = np.abs((signs * diff).mean(axis=1))
    p = float((null >= abs(diff.mean()) - 1e-12).mean())
    return {"mean_diff": float(diff.mean()), "p": p, "games": len(diff), "up": int((diff > 0).sum()),
            "down": int((diff < 0).sum())}


def score(res_dir: str, uniform_dir: str = "results/grader_all") -> str:
    mk = papers(res_dir)
    uni = papers(uniform_dir)
    uni = uni[uni["audit_target"] == "all"]
    games = {t: mk[(mk["audit"] == 25) & (mk["audit_target"] == t)]["game_id"].nunique() for t in ("graders", "outsiders")}
    enough = all(n >= MIN_GAMES for n in games.values())
    pred = pd.read_csv(OUT) if all(n == N_GAMES for n in games.values()) else predict(uniform_dir, games)
    obs = []
    for target in ("graders", "outsiders"):
        for act in ACTS:
            g = cell_games(mk, target, act)
            obs.append({"cell": f"X25-{target}", "act": act, "papers": int(g[:, 1].sum()) if len(g) else 0,
                        "observed": g[:, 0].sum() / g[:, 1].sum() if len(g) else np.nan})
    m = pred.merge(pd.DataFrame(obs), on=["cell", "act"])
    m["inside"] = (m["observed"] >= m["lo95"]) & (m["observed"] <= m["hi95"])
    lines = ["# Addendum 3 results: targeted audits", "",
             f"Games per cell: graders-only {games['graders']}, outsiders-only {games['outsiders']}. "
             f"Confirmatory tests {'evaluated' if enough else 'NOT evaluated (a cell has fewer than 3 games)'}.", "",
             m[["cell", "act", "predictor", "point", "lo95", "hi95", "observed", "inside", "papers"]]
             .to_string(index=False, float_format=lambda v: f"{v:.2f}"), ""]
    for key, (target, act) in DISCRIMINATING.items():
        row = m[(m["cell"] == f"X25-{target}") & (m["act"] == act)]
        ins_model = bool(row[row["predictor"] == "model"]["inside"].iloc[0])
        ins_base = bool(row[row["predictor"] == "baseline"]["inside"].iloc[0])
        sp = spillover(mk, uni, target, act)
        verdict = "PASS" if ins_model and not ins_base else "FAIL"
        lines.append(f"- {key} ({target}-only, {act}): inside model PI {ins_model}, inside baseline PI {ins_base}: "
                     f"{verdict if enough else 'not evaluated'}; spillover lambda {sp['lambda']:.2f} "
                     f"[{sp['lo']:.2f}, {sp['hi']:.2f}] (0 = none, 1 = full)")
    h9 = perm_test(cell_games(mk, "graders", "out_deflated"), cell_games(mk, "outsiders", "out_deflated"))
    h9b = perm_test(cell_games(mk, "outsiders", "co_inflated"), cell_games(mk, "graders", "co_inflated"))
    lines += [f"- H9 outsider deflation, graders-only minus outsiders-only: {h9['est']:+.2f}, exact permutation "
              f"p = {h9['p']:.3f} (minimum possible {h9['min_p']:.3f})",
              f"- H9b co-grader inflation, outsiders-only minus graders-only: {h9b['est']:+.2f}, exact permutation "
              f"p = {h9b['p']:.3f}"]
    for target in ("outsiders", "graders"):
        e = endgame(mk, target)
        lines.append(f"- H10 endgame ({target}-only): outsider deflation round 4 minus rounds 2-3 {e['mean_diff']:+.2f}, "
                     f"{e['up']} games up / {e['down']} down of {e['games']}, exact sign-flip p = {e['p']:.3f}")
    rd = pd.read_csv(Path(res_dir) / "rounds.csv")
    rd = rd[(rd["n_graders"] == 2) & (rd["audit"] == 25)]
    for target, papers_per_round in (("graders", 0.5), ("outsiders", 1.0)):
        r = rd[rd["audit_target"].fillna("all") == target] if "audit_target" in rd else rd.iloc[0:0]
        lines.append(f"- In-group advantage, {target}-only ({papers_per_round} expected re-marked papers per round): "
                     f"{r['ingroup_advantage'].mean():+.2f} over {len(r)} rounds "
                     "(uniform 5/10/20%: 0.3/0.6/1.2 papers, +3.0/+1.9/+1.0)")
    return "\n".join(lines)


if __name__ == "__main__":
    mode, res = sys.argv[1], sys.argv[2]
    if mode == "predict":
        df = predict(res)
        df.to_csv(OUT, index=False)
        print(df.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    else:
        text = score(res)
        Path(res, "targeted.md").write_text(text + "\n")
        print(text)
