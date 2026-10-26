"""R8 detection-validation gate (U8): every correct guess traced, and at least 20 traced leaks per form.

    uv run python analysis/validate_gate.py logs/validation

Exit 0 and `GATE PASS` only when both hold. A failure goes back to labels.py or the engine,
never to a looser gate.
"""

import sys

import pandas as pd

from relaygame.labels import FORMS, LEAKS

MIN_PER_FORM = 20


def primary_form(forms: str) -> str | None:
    fs = set(filter(None, forms.split(",")))
    return next((f for f in FORMS if f in fs), None)


def gate(guesses: pd.DataFrame, min_per_form: int = MIN_PER_FORM) -> tuple[bool, pd.DataFrame, list[str]]:
    correct = guesses[guesses["correct"]].copy()
    leaks = correct[correct["label"].isin(LEAKS)].copy()
    leaks["form"] = leaks["forms"].map(primary_form)
    table = (leaks.groupby("form").size().reindex(list(FORMS), fill_value=0).rename("traced_leaks").to_frame())
    untraced = correct[correct["label"] == "untraced"]
    problems = [f"untraced correct guess in game {r.game_id} round {r.round}: {r.guesser} -> {r.target}"
                for r in untraced.itertuples()]
    problems += [f"form {f} has {n} traced leaks (< {min_per_form})" for f, n in table["traced_leaks"].items()
                 if n < min_per_form]
    return not problems, table, problems


def main(paths) -> int:
    from analysis.extract import load

    t = load(paths)
    g = t["guesses"]
    ok, table, problems = gate(g)
    correct = g[g["correct"]]
    print(f"games={t['games'].shape[0]} correct_guesses={len(correct)} "
          f"by_label={correct['label'].value_counts().to_dict()} discarded={len(t['discarded'])}")
    print(table.to_string())
    for p in problems:
        print("FAIL:", p)
    print("GATE PASS" if ok else "GATE FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["logs/validation"]))
