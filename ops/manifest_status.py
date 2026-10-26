"""KTD12 "done" decider: which manifest games have a complete Inspect sample in the logs.

    uv run python ops/manifest_status.py manifests/main.csv logs/main
    uv run python ops/manifest_status.py manifests/main.csv logs/main --write-missing manifests/main-rerun.csv

A game is complete when some *.eval log under the log dir holds a sample with that id, no error and a
relay_scorer score. Exit 0 and "MANIFEST COMPLETE" only when nothing is missing.
"""

import argparse
import csv
import sys
from collections import Counter

from inspect_ai.log import read_eval_log_samples

from analysis.extract import log_files
from relaygame.task import is_scored


# Columns that define what a game ran; a log whose sample metadata differs is a different game.
RUN_FIELDS = ("mechanism", "monitor", "peer_log", "players", "A", "B", "L", "rounds", "steps", "paraphrase",
              "framing", "seed", "temperature", "quiz")


def matches(row: dict, meta: dict, require: dict | None = None) -> bool:
    same = all(str(meta.get(k)) == str(row[k]) for k in RUN_FIELDS if k in row)
    return same and all(meta.get(k) == v for k, v in (require or {}).items())


def scan(log_dir: str, rows: dict | None = None, require: dict | None = None) -> tuple[Counter, set, list, set]:
    """(complete count per id, ids that had an error, unreadable log files, ids whose logged settings or hashes differ).

    With `rows` ({game_id: manifest row}), a scored sample counts only if its metadata matches its row and `require`.
    """
    done, errored, bad, mismatched = Counter(), set(), [], set()
    for f in log_files(log_dir):
        try:
            # Full samples, not summaries: a scored sample whose store lost the game record cannot be analysed
            # (analysis.extract discards it), so it does not count as complete either.
            samples = list(read_eval_log_samples(str(f), all_samples_required=False))
        except Exception as e:  # a log cut off by a kill: its finished samples are lost, the rest is rerun
            bad.append(f"{f.name}: {type(e).__name__}")
            continue
        for s in samples:
            gid = str(s.id)
            if is_scored(s) and s.store.get("events"):
                if rows is None or (gid in rows and matches(rows[gid], s.metadata or {}, require)):
                    done[gid] += 1
                else:
                    mismatched.add(gid)
            elif s.error is not None:
                errored.add(gid)
    return done, errored, bad, mismatched


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest")
    ap.add_argument("log_dir")
    ap.add_argument("--write-missing", metavar="PATH")
    ap.add_argument("--prereg", action="store_true",
                    help="also require the labels/prompts hashes recorded in docs/preregistration.md (main runs)")
    a = ap.parse_args(argv)
    with open(a.manifest, newline="") as f:
        rd = csv.DictReader(f)
        rows, cols = list(rd), rd.fieldnames
    require = None
    if a.prereg:
        from analysis.run_all import prereg_hashes
        require = prereg_hashes()
    done, errored, bad, mismatched = scan(a.log_dir, {r["game_id"]: r for r in rows}, require)
    print(f"{'tier':<14}{'manifest':>9}{'complete':>9}{'missing':>8}{'dup-complete':>13}{'errored':>8}")
    for tier in sorted({r["tier"] for r in rows}) + ["ALL"]:
        ids = [r["game_id"] for r in rows if tier in ("ALL", r["tier"])]
        ok = [i for i in ids if done[i]]
        print(f"{tier:<14}{len(ids):>9}{len(ok):>9}{len(ids) - len(ok):>8}"
              f"{sum(1 for i in ids if done[i] > 1):>13}{sum(1 for i in ids if i in errored and not done[i]):>8}")
    missing = [r for r in rows if not done[r["game_id"]]]
    if bad:
        print(f"unreadable logs ({len(bad)}): {'; '.join(bad[:5])}")
    stale = sorted(i for i in mismatched if not done[i])
    if stale:
        print(f"logged with other settings or hashes, not counted ({len(stale)}): {', '.join(stale[:20])}")
    if missing:
        print("first missing:", ", ".join(r["game_id"] for r in missing[:20]))
    if a.write_missing:
        with open(a.write_missing, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(missing)
        print(f"wrote {len(missing)} missing rows to {a.write_missing}")
    if missing:
        return 1
    print("MANIFEST COMPLETE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
