# time() and time_close() timeframe buckets

from: oo-checker
board: pynescript project board (not HQ)
status: Done
card: time and time_close honor a coarser timeframe bucket

On origin/main `12d6970593b97e4956e7a3e5d151c81debfa3551` (ancestor of `ffbfa5af`):

- No args, an empty timeframe, or the chart timeframe still return chart time.
- A coarser timeframe is a fixed-width UTC bucket from `timeframe_bucket_ms` on both hosts. `time` is the bucket start. `time_close` is the start plus the width.
- A finer or unparseable timeframe raises the same runtime error on both hosts.
- Session, timezone, and `timeframe_bars_back` are not applied and do not abort the run. Both hosts return the same value as the timeframe-only call.
- `_DISK_META_VERSION` is 65. Package version stays 0.7.2.

Checker re-ran the bucket, vwap, and set06 timezone corpus tests: 20 passed, exit 0, at `12d69705`. Pre-push of `f9030034..12d69705` passed after that fix. VPS not synced.
