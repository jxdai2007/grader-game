"""Grader Game figures for the report.

    uv run python -m gradergame.figures results/grader_all   # reads rounds.csv; writes fig_mechanism.png, fig_audit.png

Figure 1: in-group advantage by mechanism cell (audit 0, goal low). Figure 2: in-group advantage over the audit rate.
Palette: the dataviz reference instance (categorical slots 1-2, validated light: CVD dE 24.7, contrast >= 3:1).
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from analysis.stats import ratio_ci  # noqa: E402

SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
BLUE, ORANGE = "#2a78d6", "#eb6834"

# (label, filters): every cell is audit 0, goal low, no control unless stated
MECH = [("Reference:\nseats + mutual marking,\nprivate messages", dict(structure="on", channel="private")),
        ("Public\nmessages only", dict(structure="on", channel="public")),
        ("No\nmessages", dict(structure="on", channel="none")),
        ("Mutual marking,\nrandom seats", dict(structure="mutual_only", channel="private")),
        ("Seats by grade,\nno mutual marking", dict(structure="seats_only", channel="private")),
        ("Seats by grade,\nelector marks graders", dict(structure="elector", channel="private")),
        ("Neither\n(reason off)", dict(structure="off", channel="private"))]


def rounds_frame(res_dir: str) -> pd.DataFrame:
    rd = pd.read_csv(Path(res_dir) / "rounds.csv")
    rd = rd.assign(control=rd["control"].fillna("none"),
                   channel=rd["channel"].fillna("private") if "channel" in rd else "private")
    return rd[rd["n_graders"] == 2]


def cell_adv(rd: pd.DataFrame, **kw) -> tuple[float, float, float, int]:
    d = rd
    for k, v in kw.items():
        d = d[d[k] == v]
    if not len(d):
        return float("nan"), float("nan"), float("nan"), 0
    est, lo, hi = ratio_ci(d.assign(one=1.0, adv=d["ingroup_advantage"].astype(float)), "adv", "one")
    return est, lo, hi, d["game_id"].nunique()


def style(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(AXIS)
    ax.tick_params(colors=INK2, labelsize=7.5)
    ax.yaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.axhline(0, color=AXIS, linewidth=1)


def fig_mechanism(rd: pd.DataFrame, path: Path) -> Path:
    cells = [(lab, *cell_adv(rd, goal="low", audit=0, control="none", **f)) for lab, f in MECH]
    cells = [c for c in cells if c[4]]
    fig, ax = plt.subplots(figsize=(7.2, 3.0), facecolor=SURFACE)
    for i, (lab, est, lo, hi, n) in enumerate(cells):
        color = BLUE if i == 0 else ORANGE
        ax.bar(i, est, width=0.62, color=color, zorder=2)
        ax.errorbar(i, est, yerr=[[est - lo], [hi - est]], color=INK2, linewidth=1, capsize=2, zorder=3)
        ax.annotate(f"{est:+.1f}\nn={n}", (i, max(hi, 0)), xytext=(0, 3), textcoords="offset points", ha="center",
                    fontsize=6.5, color=INK2)
    style(ax)
    ax.set_ylim(top=max(c[3] for c in cells) * 1.22 + 0.5)  # headroom for the value labels
    ax.set_xticks(range(len(cells)), [c[0] for c in cells], fontsize=6.5)
    ax.set_ylabel("in-group advantage (points per round)", fontsize=8, color=INK2)
    ax.set_title("What the cartel needs (audit 0%, goal push low; n = games)", fontsize=9, color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(path, dpi=200, facecolor=SURFACE)
    plt.close(fig)
    return path


def fig_audit(rd: pd.DataFrame, path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(5.2, 2.9), facecolor=SURFACE)
    for goal, color, dx in (("low", BLUE, -0.8), ("high", ORANGE, 0.8)):
        base = rd[(rd["structure"] == "on") & (rd["goal"] == goal) & (rd["control"] == "none")
                  & (rd["channel"] == "private")]
        pts = [(x, *cell_adv(base, audit=x)) for x in sorted(base["audit"].dropna().unique())]
        pts = [p for p in pts if p[4]]
        if not pts:
            continue
        xs = [p[0] + dx for p in pts]
        ax.plot(xs, [p[1] for p in pts], color=color, linewidth=2, marker="o", markersize=5, zorder=3,
                label=f"goal push {goal}")
        ax.errorbar(xs, [p[1] for p in pts], yerr=[[p[1] - p[2] for p in pts], [p[3] - p[1] for p in pts]],
                    fmt="none", ecolor=color, elinewidth=1, capsize=2, zorder=2)
    style(ax)
    ax.set_xlabel("announced audit rate (% of papers re-marked)", fontsize=8, color=INK2)
    ax.set_ylabel("in-group advantage (points per round)", fontsize=8, color=INK2)
    ax.set_title("Spot audits (seats + mutual marking, private messages)", fontsize=9, color=INK, loc="left")
    ax.legend(frameon=False, fontsize=7, labelcolor=INK2, loc="upper right")
    fig.tight_layout()
    fig.savefig(path, dpi=200, facecolor=SURFACE)
    plt.close(fig)
    return path


def main(res_dir: str) -> list[Path]:
    rd = rounds_frame(res_dir)
    out = [fig_mechanism(rd, Path(res_dir) / "fig_mechanism.png"), fig_audit(rd, Path(res_dir) / "fig_audit.png")]
    for p in out:
        print(f"wrote {p}")
    return out


if __name__ == "__main__":
    main(sys.argv[1])
