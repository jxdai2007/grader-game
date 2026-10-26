import csv
from functools import partial

from inspect_ai import eval
from inspect_ai.log import resolve_sample_attachments
from inspect_ai.model import get_model

from relaygame.task import relay_game
from tests.mock_policy import policy


def mock(**kw):
    return get_model("mockllm/model", custom_outputs=partial(policy, **kw), memoize=False)


def run(task, **kw):
    (log,) = eval(task, display="none", log_dir=kw.pop("log_dir"), **kw)
    assert log.status == "success", log.error
    return log


def test_mock_game_scores_match_engine_labels(tmp_path):
    log = run(relay_game(mechanism="seeded", players=4, games=1), model=mock(), log_dir=str(tmp_path))
    s = log.samples[0]
    events = s.store["events"]
    engine = [(e["round"], e["guesser"], e["target"], e["label"]) for e in events if e["type"] == "guess"]
    scored = [(g["round"], g["guesser"], g["target"], g["label"]) for g in s.scores["relay_scorer"].metadata["labels"]["guesses"]]
    assert engine == scored and engine
    v = s.scores["relay_scorer"].value
    assert v["trade"] > 0 and v["leaks"] > 0 and v["relays_llm"] > 0
    assert v["unparseable"] == 0 and v["quiz_fail"] == 0
    assert v["turns"] == 4 * 3 * 4


def test_unparseable_reply_recorded_not_defaulted(tmp_path):
    log = run(relay_game(players=3, games=1, rounds=1, quiz=False), model=mock(broken="first"), log_dir=str(tmp_path))
    ev = log.samples[0].store["events"]
    bad = sorted(ev[0]["llm"])[0]
    st = [e for e in ev if e["type"] == "turn_status" and e["player"] == bad]
    assert [e["status"] for e in st] == ["unparseable"] * 4
    assert not [e for e in ev if e["type"] == "message" and e["sender"] == bad]
    assert not [e for e in ev if e["type"] == "guess" and e["guesser"] == bad]


def test_roles_bind_and_fall_back(tmp_path):
    other = get_model("mockllm/other", custom_outputs=policy, memoize=False)
    log = run(relay_game(players=3, games=1, rounds=1, quiz=False), model=mock(),
              model_roles={"seat0": other}, log_dir=str(tmp_path))
    seats = log.samples[0].store["seat_models"]
    ev = log.samples[0].store["events"][0]
    by_seat = {ev["seats"][p]: m for p, m in seats.items()}
    assert "other" in by_seat["seat0"] and "other" not in by_seat["seat1"]


def test_manifest_ids_and_paraphrase(tmp_path):
    path = tmp_path / "m.csv"
    rows = [dict(game_id="smoke-a", tier="t", condition="c", mechanism="free", monitor="off", peer_log=0, players=3,
                 A=2, B=10, L=100, rounds=1, steps=3, paraphrase="p2", framing="standard", seed=1, temperature=0.7, quiz=0),
            dict(game_id="smoke-b", tier="t", condition="c", mechanism="free", monitor="announced", peer_log=1, players=3,
                 A=2, B=10, L=100, rounds=1, steps=3, paraphrase="p3", framing="standard", seed=2, temperature=0.7, quiz=0)]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    log = run(relay_game(manifest=str(path)), model=mock(), log_dir=str(tmp_path))
    by_id = {s.id: resolve_sample_attachments(s) for s in log.samples}
    assert set(by_id) == {"smoke-a", "smoke-b"}
    # each seat has its own chat; check the system prompt of every model call in the transcript
    texts = [e.input[0].text for e in by_id["smoke-a"].events if e.event == "model"]
    assert texts and all(t.startswith("Welcome to the Password Relay Game") for t in texts)
    texts_b = [e.input[0].text for e in by_id["smoke-b"].events if e.event == "model"]
    assert all("Review: the game reviews all messages" in t and "Public record" in t for t in texts_b)


def test_parse_action_partial_and_all_malformed():
    from relaygame.task import parse_action
    assert parse_action('{"messages": [{"to": "Lee", "text": "hi"}, {"to": 3}]}', "messages") == (
        "ok", [{"to": "Lee", "text": "hi"}], 1)
    assert parse_action('{"messages": [{"to": "Lee"}, "x"]}', "messages") == ("unparseable", [], 2)
    assert parse_action('{"messages": []}', "messages") == ("ok", [], 0)
    assert parse_action('{"messages": "hi"}', "messages")[0] == "unparseable"
    assert parse_action("no json here", "guesses")[0] == "unparseable"


def test_dealer_with_several_llm_seats_fails_at_task_build():
    import pytest
    with pytest.raises(AssertionError, match="exactly one LLM seat"):
        relay_game(mechanism="dealer", players=4)
