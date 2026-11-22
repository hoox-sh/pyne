# Realtime residuals still open

from: oo-chief
board: pynescript project board (not HQ)
status: Todo
card: Realtime residuals: trail high-versus-low inside one OHLC tick, update_last_bar MAE/MFE tick-accuracy, numeric nopython varip tick loop

- Trail: hosts already match. `f9030034` pins `tests/test_trail_intratick_residual.py` (4 passed). High-versus-low order inside one OHLC tick is still unmodeled. The broker was not changed for that.
- `update_last_bar` MAE/MFE stays bar-level. Not started.
- Numeric varip tick loop stays on the object-mode route. Not started.

origin/main: `ffbfa5afdd5b819d338de3dd624fc1e8452bbd22`. VPS not synced.
