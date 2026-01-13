# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

from __future__ import annotations

from itertools import zip_longest


def grouper(iterable, n, *, incomplete="fill", fillvalue=None):
    args = [iter(iterable)] * n
    match incomplete:
        case "fill":
            return zip_longest(*args, fillvalue=fillvalue)
        case "strict":
            return zip(*args, strict=True)
        case "ignore":
            return zip(*args, strict=False)
        case _:
            msg = "Expected fill, strict, or ignore"
            raise ValueError(msg)
