from gradergame.manifest import build
from gradergame.task import row_config


def test_pilot_manifest_cells_and_ids():
    rows = build("pilot", 2, 0, 4, 1)
    assert len(rows) == 12 and len({r["game_id"] for r in rows}) == 12
    assert {r["condition"] for r in rows} == {"on/low/X0", "on/high/X0", "off/low/X0", "off/high/X0", "on/high/X25",
                                              "on/low/X0/secret_team"}
    for r in rows:
        row_config(r)


def test_main_manifest_sizes_and_interleaving():
    rows = build("main", 10, 6, 4, 1, short=True, audit_games=8, controls=("secret_team", "clear_priority"))
    assert len(rows) == 4 * 10 + 4 * 8 + 2 * 6
    assert len({r["game_id"] for r in rows}) == len(rows) and len({r["seed"] for r in rows}) == len(rows)
    first = [r["condition"] for r in rows[:4]]
    assert len(set(first)) == 4  # every cause cell appears before any repeats
    assert len(build("main", 6, 0, 4, 1, cause_only=True)) == 24


def test_main_manifest_interleaves_blocks():
    rows = build("main", 10, 6, 4, 1, short=True, audit_games=8, controls=("secret_team", "clear_priority"))
    first10 = {r["condition"] for r in rows[:10]}
    assert len(first10) == 10  # 4 cause + 4 audit + 2 control cells in the first replicate
