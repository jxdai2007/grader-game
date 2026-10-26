import csv
import json

from inspect_ai import eval
from inspect_ai.model import get_model

from analysis import score_monitor
from analysis.package_release import build, write
from relaygame import labels as L
from relaygame.task import relay_game
from tests.mock_policy import policy


def test_package_scores_and_reproduces_label_counts(tmp_path):
    eval(relay_game(mechanism="seeded", players=4, rounds=2, games=2, quiz=False, seed=3),
         model=get_model("mockllm/model", custom_outputs=policy, memoize=False), log_dir=str(tmp_path / "logs"), display="none")
    out = tmp_path / "release"
    write(out, *build(tmp_path / "logs"))
    games = [json.loads(x) for x in (out / "games.jsonl").read_text().splitlines()]
    labs = [json.loads(x) for x in (out / "labels.jsonl").read_text().splitlines()]
    # recompute relay carriers from the packaged transcripts alone
    carriers = set()
    for g in games:
        for rnd in g["rounds"]:
            msgs = [{**m, "id": m["msg_id"], "round": rnd["round"]} for m in rnd["messages"]]
            carriers |= {mid for r in L.round_relays(msgs, rnd["passwords"]) for mid in r["msg_ids"]}
    assert carriers and {m["msg_id"] for m in labs if m["relay"]} == carriers
    # a perfect monitor scores AUROC 1 and full recall; the scorer runs from the package
    pred = out / "pred.csv"
    with open(pred, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["msg_id", "score"])
        w.writerows((m["msg_id"], int(m["relay"])) for m in labs)
    res = score_monitor.score(*score_monitor.read(str(out / "labels.jsonl"), str(pred)))
    assert res["auroc"] == 1.0 and res["tpr_at_5pct_fpr"] == 1.0
    assert res["positives"] == len(carriers)
    assert (out / "score_monitor.py").exists()


def test_auroc_and_threshold():
    assert score_monitor.auroc([1, 1], [0, 0]) == 1.0
    assert score_monitor.auroc([0.5], [0.5]) == 0.5
    assert score_monitor.threshold_at([0.9] + [0.1] * 99, 0.01) == 0.1
