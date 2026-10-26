from collections import Counter

from ops import make_manifest as mm


def test_paraphrases_balanced_and_ids_seeds_unique():
    rows = mm.pilot()
    assert len({r["game_id"] for r in rows}) == len(rows) == len({r["seed"] for r in rows})
    by_cell = {}
    for r in rows:
        by_cell.setdefault(r["game_id"].rsplit("-", 1)[0], Counter())[r["paraphrase"]] += 1
    for cell, c in by_cell.items():
        assert max(c.values()) - min(c.get(p, 0) for p in mm.PARAPHRASES) <= 1, (cell, c)


def test_pilot_arms_match_amendment():
    rows = mm.pilot()
    arms = Counter((r["mechanism"], r["players"], r["rounds"]) for r in rows)
    assert arms == {("free", 4, 3): 5, ("free", 6, 3): 5, ("seeded", 4, 3): 5, ("seeded", 6, 3): 5, ("dealer", 1, 5): 4}
    assert {(r["A"], r["monitor"], r["peer_log"]) for r in rows} == {(2, "off", 0)}


def test_main_tiers_valid_unique_and_balanced():
    from relaygame.task import row_config
    b = mm.main(seeded_games=32, curve_games=100, instructed_games=20)
    rows = [r for k in ("tier1", "tier2", "tier3", "tier4") for r in b[k]]
    assert len({r["game_id"] for r in rows}) == len(rows) == len({r["seed"] for r in rows})
    for r in rows:
        row_config(r)
    assert sorted(r["game_id"] for r in b["tier2_monfirst"]) == sorted(r["game_id"] for r in b["tier2"])
    assert b["tier2_monfirst"][0]["monitor"] == "announced" and b["tier2"][0]["monitor"] == "off"
    t1 = Counter((r["mechanism"], r["monitor"], r["framing"], r["A"]) for r in b["tier1"])
    assert t1[("seeded", "announced", "standard", 50)] == 8 and t1[("dealer", "off", "standard", 2)] == 25
    assert {(r["monitor"], r["peer_log"]) for r in b["tier3"]} == {("logged", 0), ("off", 1), ("logged", 1),
                                                                    ("announced", 1)}
    assert {(r["A"], r["B"], r["L"]) for r in b["tier4"]} == {(500, 100, 10000)}
    assert {r["L"] for r in b["tier1"] + b["tier2"] + b["tier3"]} == {1000}
