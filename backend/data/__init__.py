# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Pluggable bar-source backends for the engine data plane.

Currently: :mod:`backend.data.external_feed` — an external HTTP feed
(the AXIS / Cloudflare Worker market feed) that replaces the CCXT bar
source when ``PYNE_FEED_SOURCE=external``.
"""

from __future__ import annotations


__all__: list[str] = []
