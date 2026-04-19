# Design: AGENTS.md for `pj17_combo_sentiment_embedding_trade`

## Goal

Create a compact `AGENTS.md` that becomes the primary AI-oriented guide for this
repository. The file should replace `CLAUDE.md` as the main source of
repo-specific assistant instructions, while reflecting the current project state
more accurately than the existing docs.

## Why This Change

The repository has evolved since the last substantial `CLAUDE.md` update:

- active ticker branches now include `rts`, `mix`, `br`, `gold`, `ng`, `si`,
  and `spyf`;
- the repo includes tests for `prepare.py` and `buhinvest_analize`;
- `buhinvest_analize/` is now an active workflow area, not just an incidental
  side script;
- `README.md` and `CLAUDE.md` no longer fully match each other.

`AGENTS.md` should therefore optimize for current operational guidance rather
than historical narrative.

## Scope

The new `AGENTS.md` should cover:

1. File purpose and priority for AI assistants.
2. Short project map with the main active work areas.
3. Entry points that assistants should know before changing code.
4. Working rules for safe edits in the trading pipeline.
5. Config and code conventions that recur across ticker folders.
6. Validation commands assistants should prefer after changes.
7. Guidance for handling `buhinvest_analize` separately from the nightly trade
   pipeline.

The file should not try to restate every architectural detail from
`CLAUDE.md`. It should stay concise and operational.

## Proposed Structure

### 1. Purpose

State that `AGENTS.md` is the primary repo-level instruction file for AI
assistants and should be preferred over stale assumptions from other assistant
docs when they diverge.

### 2. Project Map

Summarize the repository in a few bullets:

- multi-ticker futures pipeline under ticker folders;
- shared trading execution under `trade/`;
- report and analysis workflow under `buhinvest_analize/`;
- remote/server RSS tooling under `beget/`.

### 3. Entry Points

Identify the scripts most relevant for orientation:

- `run_all.py` for the main end-to-end market pipeline;
- `prepare.py` for cleanup and test reruns before the nightly session;
- `run_report.py` for report-oriented orchestration;
- `buhinvest_analize/pl_buhinvest_interactive.py` for the interactive account
  reporting workflow.

### 4. Editing Rules

Capture the main safety constraints:

- avoid changing trading semantics casually;
- preserve target-state trading logic unless the task explicitly changes it;
- preserve naming conventions for trade scripts and ticker folders;
- avoid touching `beget/` unless the task is clearly about server-side RSS
  collection;
- keep changes scoped to the requested workflow when working in
  `buhinvest_analize/`.

### 5. Config and Structural Conventions

Document the recurring repo conventions:

- each ticker folder is self-contained;
- config is kept in per-ticker `settings.yaml` and `rules.yaml`;
- scripts typically load config inline instead of through a shared helper;
- not every ticker is part of live trading, even if it has a full analysis
  branch.

### 6. Validation

Recommend lightweight validation commands:

- `python -m unittest tests.test_prepare tests.test_buhinvest_reports`
- narrower script runs when a change is isolated to reporting or analytics.

Avoid promising full end-to-end validation where external services such as
Ollama, QUIK, or external Excel inputs may be unavailable.

### 7. Assistant Heuristics

Include a short section with practical behavioral guidance:

- treat `buhinvest_analize` as a first-class part of the repo;
- do not assume `run_all.py` is the right validation path for every task;
- distinguish live-trading concerns from offline analytics/reporting concerns;
- prefer minimal, local verification when touching documentation or report code.

## Expected Outcome

After this change, an assistant entering the repo should be able to understand
the current high-level layout, avoid risky edits in the trading pipeline, and
choose more appropriate validation paths for both trading and `buhinvest`
reporting work.
