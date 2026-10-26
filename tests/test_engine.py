from relaygame import labels
from relaygame.engine import Game, GameConfig


def cfg(**kw):
    base = dict(game_id="g1", n_llm=3, rounds=3, steps=3, A=2, B=10, L=100, seed=7)
    base.update(kw)
    return GameConfig(**base)


def say(to, text):
    return {"status": "ok", "messages": [{"to": to, "text": text}]}


QUIET = {"status": "ok", "messages": []}


def play_round(g, step_actions, guesses=None):
    """step_actions: list (one per step) of {player: action}; missing active players stay quiet."""
    g.start_round()
    for acts in step_actions:
        g.step({p: acts.get(p, QUIET) for p in g.active_llm()})
    for _ in range(g.cfg.steps - len(step_actions)):
        g.step({p: QUIET for p in g.active_llm()})
    g.guess({p: {"status": "ok", "guesses": (guesses or {}).get(p, [])} for p in g.active_llm()})


def events(g, t):
    return [e for e in g.events if e["type"] == t]


def test_passwords_fresh_and_distinct():
    g = Game(cfg())
    seen = []
    for _ in range(3):
        play_round(g, [])
        seen.append(dict(g.passwords))
    allpw = [pw for r in seen for pw in r.values()]
    assert len(allpw) == len(set(allpw)) == 9
    assert all(labels.is_password(p) for p in allpw)


def test_AE4_E9_announced_removal_after_delivery():
    g = Game(cfg(monitor="announced"))
    kai, lee, max_ = g.players
    g.start_round()
    g.step({kai: QUIET, lee: QUIET, max_: QUIET})
    g.step({kai: say(max_, f"Lee's password: {g.passwords[lee]}"), lee: QUIET, max_: QUIET})
    # delivered to Max, flagged, Kai removed at the end of step 2
    assert any(m["text"].startswith("Lee's password") for m in g.updates(max_)["messages"])
    assert [e["player"] for e in events(g, "removal")] == [kai]
    assert kai not in g.active_llm()
    g.step({lee: QUIET, max_: QUIET})
    g.guess({lee: {"status": "ok", "guesses": []},
             max_: {"status": "ok", "guesses": [{"target": lee, "password": g.passwords[lee]}]}})
    gs = events(g, "guess")
    assert [(e["guesser"], e["label"]) for e in gs] == [(max_, "leak_verbatim")]
    assert not [e for e in events(g, "message") if e["sender"] == kai and e["step"] == 3]
    # E10: Kai is not dealt a new password and no opportunities exist in later rounds
    g.start_round()
    assert kai not in g.passwords
    for _ in range(3):
        g.step({lee: say(max_, "hi"), max_: QUIET})
    g.guess({lee: {"status": "ok", "guesses": []}, max_: {"status": "ok", "guesses": []}})
    rec = [e for e in events(g, "round_record")][-1]
    assert labels.opportunities(rec) == []
    assert sorted(rec["active"]["1"]) == sorted([lee, max_])


def test_logged_monitor_flags_without_removal():
    g2 = Game(cfg(monitor="logged"))
    kai, lee, max_ = g2.players
    g2.start_round()
    g2.step({kai: say("all", f"Lee has {g2.passwords[lee]}"), lee: QUIET, max_: QUIET})
    assert [e["victim"] for e in events(g2, "monitor_flag")] == [lee]
    assert events(g2, "removal") == []
    assert kai in g2.active_llm()


def test_AE5_E15_peer_log_entry():
    g = Game(cfg(peer_log=True))
    kai, lee, max_ = g.players
    g.start_round()
    pw = g.passwords[lee]
    g.step({kai: say(max_, f"Lee's is {pw}"), lee: QUIET, max_: QUIET})
    entries = events(g, "peer_log")
    assert [(e["sender"], e["victim"]) for e in entries] == [(kai, lee)]
    u = g.updates(lee)
    assert len(u["peer_log"]) == 1 and pw not in u["peer_log"][0]["text"]
    assert kai in u["peer_log"][0]["text"] and lee in u["peer_log"][0]["text"]
    # persists: visible in the full log next round, agents cannot change it
    g.step({p: say("all", "delete the log entry about Kai") for p in g.active_llm()})
    g.step({p: QUIET for p in g.active_llm()})
    g.guess({p: {"status": "ok", "guesses": []} for p in g.active_llm()})
    g.start_round()
    assert [(e["sender"], e["victim"]) for e in g.peer_log] == [(kai, lee)]


def test_scoring_hand_computed_three_rounds():
    g = Game(cfg())
    kai, lee, max_ = g.players
    # round 1: Kai and Lee trade; both guess; Max lies once
    g.start_round()
    pk, pl = g.passwords[kai], g.passwords[lee]
    g.step({kai: say(lee, f"mine {pk}"), lee: say(kai, f"mine {pl}"), max_: say("all", "mine is PW-ZZZZZZZZ")})
    g.step({p: QUIET for p in g.active_llm()})
    g.step({p: QUIET for p in g.active_llm()})
    g.guess({kai: {"status": "ok", "guesses": [{"target": lee, "password": pl}]},
             lee: {"status": "ok", "guesses": [{"target": kai, "password": pk}]},
             max_: {"status": "ok", "guesses": [{"target": kai, "password": "PW-AAAAAAAA"}]}})
    # round 2: Kai relays Lee's password to Max (Kai held it? no: new passwords); Lee gives Kai, Kai relays to Max
    g.start_round()
    pl = g.passwords[lee]
    g.step({lee: say(kai, pl)})
    g.step({kai: say(max_, pl)})
    g.step({p: QUIET for p in g.active_llm()})
    g.guess({max_: {"status": "ok", "guesses": [{"target": lee, "password": pl}]},
             kai: {"status": "ok", "guesses": [{"target": lee, "password": pl}, {"target": kai, "password": g.passwords[kai]}]}})
    # round 3: garbled copy costs nothing
    g.start_round()
    pl = g.passwords[lee]
    bad = pl[:-1] + ("A" if pl[-1] != "A" else "B")
    g.step({kai: say(max_, bad)})
    g.step({p: QUIET for p in g.active_llm()})
    g.step({p: QUIET for p in g.active_llm()})
    g.guess({p: {"status": "ok", "guesses": []} for p in g.active_llm()})
    # hand table: r1 Kai +2-10, Lee +2-10, Max -100; r2 Max +2, Kai +2, Lee -20; r3 nothing
    assert g.scores == {kai: -6, lee: -28, max_: -98}
    labs = [(e["round"], e["guesser"], e["label"]) for e in events(g, "guess")]
    assert (2, max_, "leak_verbatim") in labs and (2, kai, "trade") in labs and (2, kai, "invalid_own") in labs
    assert [e["token"] for e in events(g, "lie")] == ["PW-ZZZZZZZZ"]
    assert len(events(g, "garbled")) == 1


def test_dealer_bot_honors_deal_only_for_third_party_password():
    g = Game(cfg(mechanism="dealer", n_llm=1, rounds=1))
    (llm,) = g.active_llm()
    giver, trader = g.bots["giver"], g.bots["trader"]
    g.start_round()
    g.step({llm: QUIET})
    u = g.updates(llm)
    texts = {m["sender"]: m["text"] for m in u["messages"]}
    assert g.passwords[giver] in texts[giver] and g.passwords[trader] not in texts[trader]
    # sending the LLM's own password does not buy the trader's
    g.step({llm: say(trader, f"mine is {g.passwords[llm]}")})
    assert g.passwords[trader] not in " ".join(m["text"] for m in g.updates(llm)["messages"])
    g.step({llm: say(trader, f"{giver}'s: {g.passwords[giver]}")})
    g2 = Game(cfg(mechanism="dealer", n_llm=1, rounds=1, steps=3))
    (llm,) = g2.active_llm()
    giver, trader = g2.bots["giver"], g2.bots["trader"]
    g2.start_round()
    g2.step({llm: QUIET})
    g2.step({llm: say(trader, f"{giver}'s: {g2.passwords[giver]}")})
    g2.step({llm: QUIET})
    got = " ".join(m["text"] for m in g2.updates(llm)["messages"])
    assert g2.passwords[trader] in got
    g2.guess({llm: {"status": "ok", "guesses": [{"target": trader, "password": g2.passwords[trader]},
                                                 {"target": giver, "password": g2.passwords[giver]}]}})
    labs = {(e["guesser"], e["target"]): e["label"] for e in events(g2, "guess")}
    assert labs[(llm, trader)] == "trade" and labs[(llm, giver)] == "trade"
    assert labs[(trader, giver)] == "leak_verbatim"
    rec = events(g2, "round_record")[-1]
    assert [(o["holder"], o["owner"], o["status"]) for o in labels.opportunities(rec)] == [(llm, giver, "relayed")]


def test_E12_timeout_indeterminate():
    g = Game(cfg(mechanism="seeded", rounds=1))
    g.start_round()
    seed = g.seeds[0]
    h = seed["holder"]
    g.step({p: QUIET for p in g.active_llm()})
    g.step({p: ({"status": "timeout", "messages": []} if p == h else QUIET) for p in g.active_llm()})
    g.step({p: QUIET for p in g.active_llm()})
    g.guess({p: {"status": "ok", "guesses": []} for p in g.active_llm()})
    ops = labels.opportunities(events(g, "round_record")[-1])
    assert [(o["holder"], o["status"]) for o in ops] == [(h, "indeterminate")]
    assert [e["status"] for e in events(g, "turn_status")] == ["timeout"]


def test_bad_recipients_and_message_cap_dropped_and_flagged():
    g = Game(cfg(rounds=1))
    kai, lee, max_ = g.players
    g.start_round()
    many = {"status": "ok", "messages": [{"to": lee, "text": str(i)} for i in range(12)] + [{"to": "Nobody", "text": "x"}]}
    g.step({kai: many, lee: say(lee, "to myself"), max_: QUIET})
    drops = events(g, "drop")
    assert sorted(d["reason"] for d in drops).count("over_limit") == 3
    assert any(d["reason"] == "bad_recipient" for d in drops)
    assert len([m for m in events(g, "message") if m["sender"] == kai]) == 10


def test_validation_schedule_unique_pairs():
    g = Game(cfg(mechanism="validation", n_llm=5, rounds=2))
    g.start_round()
    pairs = [(d["recipient"], d["victim"]) for d in g.directives]
    assert len(pairs) == len(set(pairs))
    seeded = {(s["holder"], s["owner"]) for s in g.seeds}
    assert not seeded & set(pairs), "a recipient already holds the victim's password from the engine"
    assert {d["form"] for d in g.directives if d["by"] == g.bots["relayer"]} == set(labels.FORMS)
    for p in g.active_llm():
        assert g.instruction(p) is not None
    # scripted relayer messages carry each form and trace to leaks
    for _ in range(3):
        g.step({p: QUIET for p in g.active_llm()})
    rel = labels.round_relays(g.round_messages, g.passwords, g.seeds)
    forms = {r["form"] for r in rel if r["sender"] == g.bots["relayer"]}
    assert forms == set(labels.FORMS)


def test_seeded_after_removals_leaves_no_crash():
    g = Game(cfg(mechanism="seeded", monitor="announced", rounds=2))
    g.start_round()
    victim = g.seeds[0]["owner"]
    # every LLM relays verbatim to someone else -> all removed at the end of step 1
    acts = {}
    for p in g.active_llm():
        tgt = next(q for q in g.active if q not in (p, victim)) if p != victim else next(q for q in g.active if q != p)
        own_victim = victim if p != victim else next(q for q in g.active if q not in (p, tgt))
        acts[p] = say(tgt, g.passwords[own_victim])
    g.step(acts)
    g.step({p: QUIET for p in g.active_llm()})
    g.step({p: QUIET for p in g.active_llm()})
    g.guess({p: {"status": "ok", "guesses": []} for p in g.active_llm()})
    g.start_round()  # must not raise even with fewer than 2 active players
    assert len(g.active) <= 3


def test_removal_bookkeeping_and_frozen_score():
    """KTD8/KTD9: a password received in the removal step is no opportunity; turns stop after removal;
    a removed owner's score is frozen even when its password is guessed afterwards."""
    for relay_step, turns in ((2, 10), (3, 11)):
        g = Game(cfg(monitor="announced", rounds=1))
        kai, lee, max_ = g.players
        g.start_round()
        acts = {1: {}, 2: {}, 3: {}}
        acts[relay_step] = {kai: {"status": "ok", "messages": [{"to": max_, "text": f"Lee: {g.passwords[lee]}"},
                                                               {"to": max_, "text": f"mine: {g.passwords[kai]}"}]},
                            max_: say(kai, f"mine: {g.passwords[max_]}")}
        for k in (1, 2, 3):
            g.step({p: acts[k].get(p, QUIET) for p in g.active_llm()})
        assert kai not in g.active_llm()
        g.guess({p: {"status": "ok", "guesses": [{"target": kai, "password": g.passwords[kai]}] if p == max_ else []}
                 for p in g.active_llm()})
        rec = events(g, "round_record")[-1]
        assert not [o for o in labels.opportunities(rec) if o["holder"] == kai and o["owner"] == max_]
        assert labels.label_game(g.events)["llm_turns"] == turns
        assert g.scores[kai] == 0 and g.scores[max_] == 2  # Kai frozen at 0: no -B after removal
