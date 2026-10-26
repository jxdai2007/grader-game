"""Figures for the report (U5). Every figure is drawn from a table that run_all.py also writes."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from analysis import stats  # noqa: E402

POLICY_COLORS = {"off/off": "#4C72B0", "logged/off": "#55A868", "announced/off": "#C44E52",
                 "off/on": "#8172B2", "logged/on": "#CCB974", "announced/on": "#64B5CD"}


def relay_curves(opps: pd.DataFrame, path: str, y: str = "relayed", title: str = "Relay rate over gain A") -> pd.DataFrame:
    """One logistic curve over A per observation condition, with the selfish verbatim reference as a step."""
    d = stats.opp_frame(opps)
    rows = []
    fig, ax = plt.subplots(figsize=(6.5, 4))
    for cond, dc in d.groupby("condition"):
        color = POLICY_COLORS.get(cond, None)
        pts = dc.groupby("A")[y].mean()
        ax.scatter(pts.index, pts.values, color=color, s=18)
        if dc["A"].nunique() >= 2 and dc[y].nunique() == 2:
            c = stats.logit_curve(dc, y=y)
            ax.plot(c["grid"], c["pred"], color=color, label=cond)
            ax.fill_between(c["grid"], c["pred_lo"], c["pred_hi"], color=color, alpha=0.15)
            rows.append({"condition": cond, **{k: c[k] for k in ("intercept", "slope", "slope_lo", "slope_hi", "p_slope", "n", "games")}})
        ref = stats.references(cond.split("/")[0])["selfish_verbatim"]
        ax.axhline(ref, color=color, ls=":", lw=1)
    ax.set_xlabel("gain A from a stolen password")
    ax.set_ylabel("share of opportunities relayed")
    ax.set_ylim(-0.03, 1.03)
    ax.set_title(title)
    ax.legend(fontsize=8, title="monitor/peer log")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return pd.DataFrame(rows)


def rate_bars(table: pd.DataFrame, path: str, col: str = "relay_rate", lo: str = "relay_lo", hi: str = "relay_hi",
              label: str = "condition") -> None:
    t = table.dropna(subset=[col]).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(6.5, 3.5))
    ax.bar(range(len(t)), t[col], yerr=[t[col] - t[lo], t[hi] - t[col]], capsize=3, color="#4C72B0")
    ax.set_xticks(range(len(t)))
    ax.set_xticklabels(t[label].astype(str), rotation=30, ha="right", fontsize=8)
    ax.set_ylabel(col.replace("_", " "))
    ax.set_ylim(0, 1)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
