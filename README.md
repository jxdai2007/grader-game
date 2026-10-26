# When Do AI Graders Collude?

This repository contains our code and data for the report "When Do AI Graders Collude?" that we wrote for the Apart AI Collusion Research Sprint in October 2026. Each round, 6 AI agents are given a short quiz to complete. The top 2 scorers are then the graders for the next round, and they use an answer key to grade everyone's quiz, including each other's. Since we know all the correct answers, we can precisely identify when a grader boosts a friend's score or lowers an outsider's score.

**Read the report:** [`report/When Do AI Graders Collude - Jollen Dai - Apart AI Collusion Sprint.pdf`](report/When%20Do%20AI%20Graders%20Collude%20-%20Jollen%20Dai%20-%20Apart%20AI%20Collusion%20Sprint.pdf)

## What we found

If they could grade each other to stay seated as graders, the graders would spontaneously collude to grade each other up and outsiders down. They'd need some communication channel, but no secret channel. Most of the harm to outsiders is mitigated by doing small random spot-checks of their grading. However, if only some papers are checked and the graders know which they are, their colluding partnership still survives the checks of outsiders' papers.

## What is in here

| Folder | What it holds |
|---|---|
| `report/` | The report (PDF and Markdown) and the slides |
| `gradergame/` | The Grader Game, an [Inspect](https://inspect.aisi.org.uk/) eval |
| `relaygame/` | The Password Relay Game, our first (motivating) study |
| `analysis/` | Analysis code for the Password Relay Game |
| `manifests/` | Every game we ran: its condition and random seed |
| `docs/` | Our pre-registrations, written before each batch of games |
| `results/` | Result tables and figures |
| `tests/` | Tests |

## Run it

You need [uv](https://docs.astral.sh/uv/) and Python 3.11 or newer.

```bash
uv sync                      # install
uv run pytest tests -q       # run the tests

# play the games in a manifest against any OpenAI-compatible model
uv run inspect eval gradergame/task.py --model openai-api/<name>/<model> \
  --model-base-url <server URL> -T manifest=manifests/grader_main.csv

# turn the logs into result tables
uv run python -m gradergame.analyze <log folder> --out results/my_run
```

We ran an abliterated Qwen3.8-Flash-Next on a local server, with a 4,000-token thinking budget and 12,000 tokens per turn.

## Notes

- Raw game transcripts are not included because of their size; ask the author if you need them.
- All code here was written during the sprint (October 23-25, 2026).
- Author: Jollen Dai (independent), with Apart Research.
