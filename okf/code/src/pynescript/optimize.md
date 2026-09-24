---
type: "Code Module"
title: "src/pynescript/optimize"
description: "Strategy hyperparameter search (TPE / random / grid + walk-forward)."
resource: "src/pynescript/optimize"
tags: [code, optimize, pynescript]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:40:25Z
sources:
  - id: tree
    resource: "src/pynescript/optimize"
    title: "src/pynescript/optimize"
    author: process:git
okf_lock: generated
---

# Files

* `__init__.py`
* `events_score.py` — build_strategy_stats
* `objective.py` — parse_objective, score_stats
* `samplers.py` — BaseSampler, GridSampler, RandomSampler, TPESampler, make_sampler, parse_sampler
* `space.py` — clamp_params, clamp_value, grid_size, param_from_mapping, space_from_input_defs, space_from_payload
* `study.py` — StudyCancelled, TooManyRuns, is_strategy_script, run_once, run_study
* `types.py` — ParamSpec, SearchSpace, StrategyStats, StudyResult, TrialResult, ValidationSpec
* `walk_forward.py` — apply_warmup, estimated_runs, holdout_split, rolling_windows
