import csv

from inspect_ai import eval
from inspect_ai.model import get_model

from ops.manifest_status import main
from relaygame.task import relay_game
from tests.mock_policy import policy

ROW = dict(tier="t", condition="c", mechanism="free", monitor="off", peer_log=0, players=3, A=2, B=10, L=100,
           rounds=1, steps=3, paraphrase="p1", framing="standard", seed=1, temperature=0.7, quiz=0)


def write(path, ids):
    rows = [dict(game_id=i, **ROW) for i in ids]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return str(path)


def play(tmp_path, ids, logs):
    m = get_model("mockllm/model", custom_outputs=policy, memoize=False)
    (log,) = eval(relay_game(manifest=write(tmp_path / "play.csv", ids)), model=m, log_dir=str(logs), display="none")
    assert log.status == "success", log.error


def test_complete_missing_and_duplicates(tmp_path, capsys):
    logs = tmp_path / "logs"
    play(tmp_path, ["g1", "g2"], logs / "b1")
    full = write(tmp_path / "full.csv", ["g1", "g2"])
    assert main([full, str(logs)]) == 0 and "MANIFEST COMPLETE" in capsys.readouterr().out

    short = write(tmp_path / "short.csv", ["g1", "g2", "g3"])
    out_csv = tmp_path / "missing.csv"
    assert main([short, str(logs), "--write-missing", str(out_csv)]) == 1
    out = capsys.readouterr().out
    assert "first missing: g3" in out and "MANIFEST COMPLETE" not in out
    assert [r["game_id"] for r in csv.DictReader(open(out_csv))] == ["g3"]

    play(tmp_path, ["g1"], logs / "b2")  # g1 now has two complete logs: counted once
    assert main([short, str(logs)]) == 1
    all_row = next(l for l in capsys.readouterr().out.splitlines() if l.startswith("ALL"))
    assert all_row.split() == ["ALL", "3", "2", "1", "1", "0"]


def test_game_logged_with_other_settings_is_not_complete(tmp_path, capsys):
    logs = tmp_path / "logs"
    play(tmp_path, ["g1"], logs)
    path = tmp_path / "reseeded.csv"
    with open(path, "w", newline="") as f:  # same id, regenerated with a different seed
        w = csv.DictWriter(f, fieldnames=["game_id", *ROW])
        w.writeheader()
        w.writerow(dict(game_id="g1", **{**ROW, "seed": 99}))
    assert main([str(path), str(logs)]) == 1
    out = capsys.readouterr().out
    assert "first missing: g1" in out and "not counted (1): g1" in out
