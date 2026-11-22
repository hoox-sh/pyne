# strategy calc_on switches stay accepted and ignored

from: oo-chief
board: pynescript project board (not HQ)
status: Blocked
card: strategy calc_on switches are accepted and ignored

A worktree commit `3be7911a` raised `RuntimeError: strategy() <name> cannot be enabled; PYNE only runs with <name>=false` when any of these is true:

- calc_on_every_tick
- calc_on_order_fills
- calc_on_every_history_tick
- process_orders_on_close
- use_bar_magnifier

That commit was not landed. Two suite scripts must still run:

- `tests/data/set02/strategies/071_str_multi_vwap_crossover.pine` sets `use_bar_magnifier = true` (`test_multi_vwap_071_parity` requires status OK or fill_background_only).
- `tests/data/set01/strategies/075_str_machine_learning_perceptron_based_strategy_v_3.pine` sets `process_orders_on_close=true` (`test_perceptron_scripts_no_ta_dmi_run_fail` asserts no error).

About 862 other files under `tests/data` set one of the five switches. Omitted or false still matches current once-per-bar, fill-on-next-bar behavior.

Need: leave the switches accepted and ignored, or schedule a real implementation. A hard error fails scripts the suite already runs.

origin/main at the time of the refusal: `ffbfa5afdd5b819d338de3dd624fc1e8452bbd22`. VPS not synced.
