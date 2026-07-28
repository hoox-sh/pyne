# Copyright (C) 2024-2026 jango_blockchained
#
# This file is part of pynescript.
#
# pynescript is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pynescript is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# Google Cloud Cost Estimate — Pynescript Server

**Author:** jango-blockchained  
**Date:** April 11, 2026  
**Status:** Draft

---

## Architecture

```
Client (VS Code LSP) → Cloud Run (Flask API)
                          ├── /run              — script execution
                          ├── /preview/chart    — chart thumbnails
                          ├── /backtest/quick   — quick backtest
                          └── /auth/validate    — API key check
                          ├── Cloud SQL (PostgreSQL) — user/API key DB
                          ├── Memorystore (Redis)    — result cache
                          └── Cloud Storage            — chart PNGs / thumbnails
```

CI/CD: Cloud Build → Artifact Registry → Cloud Run (already configured in `cloudbuild.yaml`)

---

## Monthly Cost Breakdown

| Service | Tier | What it does | Est. Cost |
|---------|------|-------------|-----------|
| **Cloud Run** | Serverless | Flask API, pay-per-use | **$30–150/mo** |
| **Cloud SQL** | db-f1-micro (1 vCPU, 0.6GB) | User accounts, API keys, usage logs | **$20–50/mo** |
| **Artifact Registry** | Basic host | Docker image storage | **$0–5/mo** |
| **Cloud Build** | Per minute | CI/CD on push | **$0–10/mo** |
| **Cloud Storage** | Standard | Chart PNGs, thumbnails | **$0–5/mo** |
| **Memorystore** | Basic (1GB) | Redis cache for chart results | **$0–40/mo** |
| **Cloud CDN / Load Balancer** | — | (not needed for MVP) | **$0** |

> Cloud Run free tier: **2M requests**, **400K CPU-seconds**, **200K GB-seconds** per month.

---

## Scenario-Based Estimates

| Scale | Pro Users | Requests/mo | Cloud Run CPU-sec | **Total/mo** |
|-------|-----------|------------|-------------------|-------------|
| **Free tier** | 0 | 0 | 0 | **$0** (within free tier) |
| **MVP** | 10 | 500K | ~500K CPU-sec | **~$50** |
| **Growth** | 50 | 2.5M | ~2.5M CPU-sec | **~$120** |
| **Scale** | 200 | 10M | ~10M CPU-sec | **~$350** |

> Assumes ~2–5 CPU-seconds per script execution request. Python interpreter + evaluator uses ~200–400MB per concurrent instance. GPU is not needed.

---

## Key Cost Drivers

1. **Script execution time** — Each `/run` or `/backtest` call runs the Python evaluator over OHLCV bars. This is the dominant cost. A typical backtest over 1,000 bars = ~2–5 CPU-seconds.
2. **Memory** — Python interpreter + evaluator needs ~200–400MB per concurrent request. Cloud Run autoscales instances accordingly.
3. **Database** — Cloud SQL is the second biggest line item. Could swap for Cloudflare D1 or PlanetScale for cheaper at early stages.
4. **Caching** — Without Redis caching, every backtest request hits the evaluator. With 1-hour TTL cache on backtest results, expect 60–70% reduction in evaluator calls.

---

## Optimization Strategies

| Strategy | Savings | Trade-off |
|----------|---------|-----------|
| Cache backtest results in Redis (1hr TTL) | 60–70% on evaluator requests | +$40/mo Memorystore |
| Queue backtests via Cloud Tasks | Smooths traffic peaks, smaller Cloud Run instances | Adds ~10s latency |
| 1 always-on min instance on Cloud Run | Faster cold starts | +$10/mo |
| Use Cloudflare D1 instead of Cloud SQL | ~$5/mo vs $20–50/mo | SQLite limitations |
| Pre-generate chart thumbnails async | Reduces on-demand CPU | Extra storage cost |
| Batch OHLCV data preprocessing | Fewer evaluator calls | Complexity in client |
| Scale-to-zero during off-peak | Lower avg cost | Cold start latency |

---

## Recommendation

**Start with ~$50–80/mo** (Cloud Run + Cloud SQL micro).

1. **Month 1–3 (MVP):** Cloud Run + Cloud SQL micro. No caching yet. Monitor request patterns.
2. **Month 3–6 (Growth):** Add Memorystore Redis with 1-hour TTL. Use Cloud Tasks for backtest queueing.
3. **Month 6+ (Scale):** At 200+ pro users, consider migrating Cloud SQL to PlanetScale or Neon for ~$25/mo instead of Cloud SQL.

---

## Free Tier Leverage

| Resource | Free Limit | How to Use |
|----------|-----------|-----------|
| Cloud Run | 2M requests, 400K CPU-sec, 200K GB-sec/mo | Free for hobby tier users; offset paid tier too |
| Cloud Build | 120 build-minutes/day | CI/CD on main branch pushes |
| Cloud Storage | 5GB, 1GB network egress/mo | Store chart thumbnails |
| Artifact Registry | 0.5GB storage | Docker images |
| Cloud SQL | 1 instance-month (db-f1-micro, 30 days) | First month free trial |

> A hobby-tier deployment with <10 active users can run entirely within free tier limits.

---

## Alternative Hosting Options

| Provider | Est. Cost | Notes |
|----------|-----------|-------|
| **Railway** | $5–50/mo | Simpler than GCP; scales automatically |
| **Render** | $7–50/mo | Python support, automatic deploys |
| **Fly.io** | $5–40/mo | Edge deployment, faster cold starts |
| **Vercel Functions** | $0–50/mo | Generous free tier, serverless Python |
| **AWS Lambda** | $0–50/mo | Pay-per-invoke; egress costs add up |
| **Self-hosted (VPS)** | $5–20/mo | Full control; no auto-scaling |
