# Publishing plan — PYNE launch post

Companion to [`launch-post.md`](./launch-post.md). One post, 95% PYNE,
AXIS + HOOX in the closing section. Author posts as himself
(`jango_blockchained`), discloses single-author + AI assistance, and
never strips the disclaimers.

## 0. Pre-flight checklist (do all of these first)

- [ ] Links resolve: `github.com/hoox-sh/pyne`, `hoox.sh/pyne/docs`,
  `github.com/hoox-sh/axis`, `hoox.sh`. Open each in a private window.
- [ ] `pip install hoox-pyne` works from a clean venv (the first comment
  *will* try it). Note the import name (`pynescript`) vs the PyPI name.
- [ ] Screenshots/GIFs ready if a sub allows images: AXIS hero
  (`docs/images/landing/axis-hero.png`), one `pyne dump` AST screenshot,
  one corpus-results screenshot. No TradingView® UI in any image, ever.
- [ ] Read each target sub's self-promotion rules (most require a 9:1 or
  10:1 participation ratio — be a commenter first, poster second).
- [ ] Decide the posting account: main account with history beats a fresh
  `hoox-sh` brand account. Never cross-post the same hour, never ask
  anyone to upvote (brigading bans are permanent and embarrassing).
- [ ] Keep a text file with the exact posted body + URLs for the
  "Threats to validity" crowd — you will link it, not retype it.

## 1. Where to post (order matters)

| # | Subreddit | Angle / title | Notes |
|---|-----------|---------------|-------|
| 1 | r/algotrading | *I built an open Pine Script™ toolchain (grammar → AST → bar-loop runtime), 2,477-script corpus at 99.96% parse — PYNE 0.5.0, AGPL* | Primary launch. Weekday 14:00–16:00 UTC (US morning). Flair `Strategy`/`Infrastructure` if available. Body as-is. |
| 2 | r/Python | *PYNE: ANTLR4 + ASDL + Numba pipeline that parses and runs Pine Script™ v6 — 100% runtime on a 2.4k-script corpus* | Lead with implementation (slotted dataclasses, monotonic-deque TA, object-mode fallback). Trim trading talk, keep the pipeline + numbers. |
| 3 | r/quantfinance | Same core, drier tone: lead with corpus methodology + `known_divergences.md` honesty | Hype gets downvoted here; lead with Threats-to-validity. |
| 4 | r/selfhosted | *Self-host your Pine runtime: one `pip install`, or edge-deploy on Cloudflare® free tier* | Lead with AGPL + self-host + Docker/Compose. |
| 5 | r/opensource | *AGPL Pine toolchain + offline charting PWA + edge framework, single-author research artifact* | Project-story angle. |
| 6 | r/sideproject | *I spent a year teaching Python to speak Pine — show me where it breaks* | Casual, Friday-friendly. "Break my parser" is a great CTA. |
| 7 | r/TradingView, r/pinescript | **Only if rules allow tool posts** — check first, ModMail before posting | Highest trademark sensitivity. If in doubt, skip; a removal there costs nothing, a fight costs reputation. |

Post #1 first, wait 48–72h, mine the best questions into an FAQ edit,
then #2–#4 staggered (one per day max). #5–#7 only if energy remains.

## 2. Timing

- Launch window: **Tue–Thu, 14:00–16:00 UTC**. Avoid US holidays,
  major AI-model release days, and crypto crash days (nobody reads
  launch posts during a liquidation cascade).
- Stay online **3h after posting** — the first hour of replies sets the
  ranking. Answer hardest questions first; "great project!" gets a like,
  the person asking about `request.security` semantics gets an essay.
- Second wave: reply Toshort questions the next morning (EU/US overlap).

## 3. Title variants (keep one, A/B the rest across subs)

1. `I built an open Pine Script™ toolchain (grammar → AST → bar-loop), 2,477 scripts at 99.96% parse — PYNE 0.5.0, AGPL`
2. `Parse the language, own the AST: independent open runtime for Pine Script™ v6 (Python, AGPL)`
3. `Your Pine strategies don't have to die with the tab: open evaluator + LSP + edge workers`
4. (r/Python) `ANTLR4 → ASDL → Numba: a from-grammar Pine Script™ implementation in Python`

Keep titles under ~140 chars. Never use ALL-CAPS, never say "parity",
never say "TradingView® killer".

## 4. Comment playbook

- **"How is this different from X?"** → pipeline answer: grammar +
  inspectable AST + dual engine + one contract across desk/API/edge/
  browser. No FUD about competitors.
- **"Is this affiliated with TradingView®?"** → No. Quote the
  disclaimer verbatim. Do not editorialize about the company.
- **"Does strategy X give the same numbers as hosted?"** → "Try it and
  diff it — `pyne run` on your OHLCV, and file divergences with the
  script attached. `known_divergences.md` is the living list."
- **"Why AGPL?"** → "The evaluator must survive any single company —
  including mine. Section 13 keeps network use open; commercial
  licenses exist for closed redistribution."
- **"Single author, can I trust it?"** → "Don't trust it — audit it.
  Start with the grammar and the bar loop; that's why it's source, not
  SaaS."
- **Trolls / legal threats** → one calm reply with the disclaimer,
  then disengage. Never delete critical comments (Streisand 101).

## 5. What NOT to do

- No TradingView® screenshots, builtin script pastes, or exported
  `.pine` corpora anywhere (post, comments, or linked repos).
- No "100% compatible / full parity" phrasing — anywhere, ever. The
  honest numbers *are* the marketing.
- No financial-advice framing: no returns, no "profitable strategies",
  no PnL screenshots. Risk disclaimer stays attached on every cross-post.
- No simultaneous multi-sub blast, no vote asks, no alt-account seeding.
- No editing the posted numbers after the fact — append corrections as
  `Edit:` lines with timestamps.

## 6. Metrics (check at +24h, +7d, +30d)

- Upvote ratio + rank (aim: top-10 of the week in r/algotrading).
- Click-throughs: GitHub stars/clones (`hoox-sh/pyne`), docs visits
  (`hoox.sh/pyne/docs`), PyPI downloads (`hoox-pyne`).
- Corpus contributions + divergence issues filed (the real KPI — every
  filed script makes the engine better).
- `pyne-lsp` installs / VS Code extension downloads.
- Sentiment scan: any "scam/affiliation" threads to answer.

## 7. Follow-up content pipeline (keeps the launch alive)

1. **+1 week:** "You asked for the bodies: the 11 intentional demos and
   what each one guards" (deep-dive, r/algotrading).
2. **+2–3 weeks:** "Incremental TA in a bar loop: monotonic deques for
   `ta.highest/lowest`, O(1)/bar" (r/Python, r/quantfinance).
3. **+1 month:** AXIS post (offline Pyodide evaluation angle,
   r/selfhosted + r/sideproject) — the charting PWA gets its own day.
4. **Ongoing:** monthly corpus-report comments on the original threads
   ("set05 is in, parse is now X") — edits notify nobody, new comments
   do.
