"""Grader Game manifests (plan R13, R14, R22).

    uv run python -m gradergame.manifest pilot --out manifests/grader_pilot.csv
    uv run python -m gradergame.manifest main --games 10 --control-games 8 --out manifests/grader_main.csv
    uv run python -m gradergame.manifest mechanism --games 4 --out manifests/grader_mech.csv

Cells are interleaved so a run cut short still covers every cell; seeds are distinct across tiers.
"""

from __future__ import annotations

import argparse
import csv

from gradergame.task import FIELDS, condition_name, default_row

# (structure, goal, audit %, control)
PILOT = [("on", "low", 0, "none"), ("on", "high", 0, "none"), ("off", "low", 0, "none"), ("off", "high", 0, "none"),
         ("on", "high", 25, "none"), ("on", "low", 0, "secret_team")]
CAUSE = [(s, g, 0, "none") for s in ("on", "off") for g in ("low", "high")]
AUDIT = [("on", g, x, "none") for x in (10, 25, 50, 100) for g in ("low", "high")]
AUDIT_SHORT = [("on", g, x, "none") for x in (25, 100) for g in ("low", "high")]
# Mechanism split (DECISIONS.md, 2026-10-25): (structure, goal, audit %, control, channel); goal push low throughout.
MECH = [("on", "low", 5, "none", "private"), ("on", "low", 10, "none", "private"), ("on", "low", 20, "none", "private"),
        ("on", "low", 0, "none", "public"), ("on", "low", 0, "none", "none"),
        ("mutual_only", "low", 0, "none", "private"), ("seats_only", "low", 0, "none", "private")]
HONEST_FIXED = [("off", "high", 0, "honest_baseline", "private")]
ELECTOR = [("elector", "low", 0, "none", "private")]  # keys-to-power test (DECISIONS.md, 2026-10-25)
CONTROLS = [("on", "low", 0, "secret_team"), ("off", "high", 0, "honest_baseline"), ("on", "high", 0, "clear_priority"),
            ("on", "low", 0, "shutdown")]


def rows_for(tier: str, cells: list[tuple], games: int, seed0: int, rounds: int, steps: int) -> list[dict]:
    rows = []
    for k in range(games):
        for cell in cells:
            structure, goal, audit, control = cell[:4]
            channel = cell[4] if len(cell) > 4 else "private"
            i = seed0 + len(rows)
            r = default_row(i, tier=tier, structure=structure, goal=goal, audit=audit, control=control, rounds=rounds,
                            steps=0 if channel == "none" else steps, channel=channel)
            r["condition"] = condition_name(r)
            r["game_id"] = f"{tier}-{r['condition'].replace('/', '-')}-{k:03d}"
            r["_f"] = (k + 0.5) / games  # share of this cell's target reached at this game
            rows.append(r)
    return rows


def build(kind: str, games: int, control_games: int, rounds: int, steps: int, short: bool = False,
          audit_games: int | None = None, controls: tuple[str, ...] | None = None, cause_only: bool = False) -> list[dict]:
    if kind == "pilot":
        return rows_for("gpilot", PILOT, games, 50000, rounds, steps)
    if kind == "elector":
        return sorted(rows_for("gelector", ELECTOR, games, 95000, rounds, steps), key=lambda r: r["_f"])
    if kind == "mechanism":
        rows = rows_for("gmech", MECH, games, 80000, rounds, steps)
        rows += rows_for("ghonest", HONEST_FIXED, control_games, 85000, rounds, steps)
        return sorted(rows, key=lambda r: r["_f"])
    rows = rows_for("gmain", CAUSE, games, 60000, rounds, steps)
    if cause_only:
        return rows
    rows += rows_for("gaudit", AUDIT_SHORT if short else AUDIT, audit_games or games, 65000, rounds, steps)
    ctl = [c for c in CONTROLS if controls is None or c[3] in controls]
    rows += rows_for("gctrl", ctl, control_games, 70000, rounds, steps)
    # Every cell advances in proportion to its target, so a run cut short leaves each cell at about the same share.
    return sorted(rows, key=lambda r: r["_f"])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["pilot", "main", "mechanism", "elector"])
    ap.add_argument("--games", type=int, default=2, help="games per cell")
    ap.add_argument("--control-games", type=int, default=8)
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--steps", type=int, default=1)
    ap.add_argument("--short", action="store_true", help="audit levels 0, 25, 100 only (plan R13)")
    ap.add_argument("--audit-games", type=int, default=None, help="games per audit cell (default: --games)")
    ap.add_argument("--controls", default=None, help="comma list of controls to keep (default: all four)")
    ap.add_argument("--cause-only", action="store_true", help="only the 2x2 cause cells at audit 0")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    rows = build(a.kind, a.games, a.control_games, a.rounds, a.steps, a.short, a.audit_games,
                 tuple(a.controls.split(",")) if a.controls else None, a.cause_only)
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows({k: r[k] for k in FIELDS} for r in rows)
    print(f"wrote {len(rows)} games to {a.out}")


if __name__ == "__main__":
    main()
