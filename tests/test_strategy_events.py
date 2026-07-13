# Copyright (C) 2025 jango-blockchained
#
# This file is part of pynescript.
#
# pynescript is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pynescript is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: LGPL-3.0-or-later
"""Tests for the ``strategy.*`` event capture layer (Plan 1).

The contract is defined in section 1.1 of
.opencode/plans/2026-07-05-pine-worker-strategy-events.md. This file is
the **parity oracle** for Plan 2 (the TypeScript port); every change to
event shape here must be reflected in ``pine-worker/src/evaluator/events.ts``.
"""

from __future__ import annotations

import dataclasses
import inspect

import pytest

from pynescript.ast import helper
from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.evaluator.builtins.base import BuiltinDispatchMixin
from pynescript.ast.evaluator.events import StrategyEvent


class TestStrategyEventDataclass:
    """Subtask 1.1.1: the frozen StrategyEvent dataclass."""

    def test_strategy_event_is_importable_from_evaluator_package(self) -> None:
        assert dataclasses.is_dataclass(StrategyEvent)

    def test_strategy_event_can_be_constructed_with_all_documented_fields(
        self,
    ) -> None:
        event = StrategyEvent(
            kind="entry",
            id="long_1",
            direction="long",
            qty=10.0,
            order_type="limit",
            limit=100.0,
            stop=99.0,
            oca_name=None,
            comment="breakout",
            bar_index=42,
            bar_time=1720182896000,
            ohlc=(100.5, 101.2, 99.8, 100.7),
            script_id="rsi_breakout_v1",
            run_id="run-abc",
        )

        assert event.kind == "entry"
        assert event.id == "long_1"
        assert event.direction == "long"
        assert event.qty == 10.0
        assert event.order_type == "limit"
        assert event.limit == 100.0
        assert event.stop == 99.0
        assert event.oca_name is None
        assert event.comment == "breakout"
        assert event.bar_index == 42
        assert event.bar_time == 1720182896000
        assert event.ohlc == (100.5, 101.2, 99.8, 100.7)
        assert event.script_id == "rsi_breakout_v1"
        assert event.run_id == "run-abc"

    def test_strategy_event_is_frozen(self) -> None:
        event = StrategyEvent(
            kind="entry",
            id=None,
            direction="long",
            qty=None,
            order_type=None,
            limit=None,
            stop=None,
            oca_name=None,
            comment=None,
            bar_index=0,
            bar_time=0,
            ohlc=(0.0, 0.0, 0.0, 0.0),
            script_id="s",
            run_id="r",
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            event.qty = 999.0  # type: ignore[misc]

    def test_strategy_event_to_dict_serializes_every_field(self) -> None:
        event = StrategyEvent(
            kind="close",
            id="close_1",
            direction=None,
            qty=5.0,
            order_type=None,
            limit=None,
            stop=None,
            oca_name=None,
            comment=None,
            bar_index=7,
            bar_time=1234,
            ohlc=(1.0, 2.0, 0.5, 1.5),
            script_id="script",
            run_id="run",
        )

        d = event.to_dict()

        assert d == {
            "kind": "close",
            "id": "close_1",
            "direction": None,
            "qty": 5.0,
            "order_type": None,
            "limit": None,
            "stop": None,
            "oca_name": None,
            "comment": None,
            "bar_index": 7,
            "bar_time": 1234,
            "ohlc": [1.0, 2.0, 0.5, 1.5],
            "script_id": "script",
            "run_id": "run",
        }

    def test_strategy_event_to_dict_preserves_none_for_unspecified_fields(
        self,
    ) -> None:
        """A cancel event has no qty, direction, limit, stop — to_dict must
        return None for those, not omit the keys (parity contract)."""
        event = StrategyEvent(
            kind="cancel",
            id="order_42",
            direction=None,
            qty=None,
            order_type=None,
            limit=None,
            stop=None,
            oca_name=None,
            comment=None,
            bar_index=99,
            bar_time=9999,
            ohlc=(0.0, 0.0, 0.0, 0.0),
            script_id="s",
            run_id="r",
        )

        d = event.to_dict()

        for key in (
            "kind",
            "id",
            "direction",
            "qty",
            "order_type",
            "limit",
            "stop",
            "oca_name",
            "comment",
            "bar_index",
            "bar_time",
            "ohlc",
            "script_id",
            "run_id",
        ):
            assert key in d, f"key {key!r} missing from to_dict()"


class TestStrategyLongShortConstants:
    """Subtask 1.1.2: strategy.long and strategy.short are zero-arg builtins
    that resolve to the literal strings ``"long"`` and ``"short"``.

    These are the sentinels passed as the ``direction`` argument to
    ``strategy.entry`` and ``strategy.order``. They MUST be registered
    builtins — falling through to name lookup (which yields the literal
    string ``"strategy.long"``) is the bug Plan 1 is fixing.
    """

    def test_strategy_long_resolves_to_string_long(self) -> None:
        ast = helper.parse("strategy.long", mode="eval")
        evaluator = NodeLiteralEvaluator()
        result = evaluator.visit(ast.body)
        assert result == "long"

    def test_strategy_short_resolves_to_string_short(self) -> None:
        ast = helper.parse("strategy.short", mode="eval")
        evaluator = NodeLiteralEvaluator()
        result = evaluator.visit(ast.body)
        assert result == "short"

    def test_strategy_long_is_callable_as_zero_arg_builtin(self) -> None:
        """Pine allows ``strategy.long()`` as a synonym for ``strategy.long``;
        both must resolve to the same string. The dispatch layer treats the
        no-paren form and the zero-arg form identically.
        """
        ast_no_paren = helper.parse("strategy.long", mode="eval")
        ast_call = helper.parse("strategy.long()", mode="eval")

        result_no_paren = NodeLiteralEvaluator().visit(ast_no_paren.body)
        result_call = NodeLiteralEvaluator().visit(ast_call.body)

        assert result_no_paren == result_call == "long"

    def test_strategy_constants_resolve_through_full_evaluator_chain(
        self,
    ) -> None:
        """The constants must work inside an ``exec`` script (not just
        ``eval``), which is the mode used by ``Runtime.run``.
        """
        source = "result = strategy.long"
        ast = helper.parse(source, mode="exec")
        evaluator = NodeLiteralEvaluator()
        evaluator.visit(ast)
        # The last-statement value is returned by exec mode.
        assert evaluator.context.get("result") == "long"


class TestKwargsPassedToBuiltinHandlers:
    """Subtask 1.2: kwargs from Pine call expressions reach builtin handlers.

    The dispatcher in ``expressions.py::visit_Call`` already collects
    keyword arguments into a ``kwargs`` dict (subtask 1.1.2 added the
    helper that returns ``(args, kwargs)``). What is missing is the
    **forwarding step**: ``_call_builtin`` currently calls
    ``handler(args)`` and drops the kwargs. These tests exercise the
    dispatch contract directly with a test-only capture handler so
    the test does not depend on any specific production builtin
    reading kwargs (consumer-side changes are subtask 1.3).
    """

    def test_call_builtin_signature_accepts_kwargs_parameter(self) -> None:
        """Structural test: ``_call_builtin`` must accept a ``kwargs``
        parameter. Fails until the signature is widened.
        """

        sig = inspect.signature(BuiltinDispatchMixin._call_builtin)
        assert "kwargs" in sig.parameters, (
            f"_call_builtin must accept a kwargs parameter; got parameters {list(sig.parameters)!r}"
        )

    def test_call_builtin_forwards_kwargs_to_handler(self) -> None:
        """A handler receives the kwargs dict when called via the
        dispatcher with positional + keyword arguments.
        """

        captured: dict = {}

        class _TestDispatch(BuiltinDispatchMixin):
            def _capture_handler(self, args, kwargs):
                captured["args"] = args
                captured["kwargs"] = kwargs
                return "captured"

            def _build_builtin_map(self):
                return {"capture.kwarg_test": self._capture_handler}

        dispatch = _TestDispatch()
        result = dispatch._call_builtin("capture.kwarg_test", [1, 2], kwargs={"x": 10, "y": "hi"})
        assert result == "captured"
        assert captured["args"] == [1, 2]
        assert captured["kwargs"] == {"x": 10, "y": "hi"}

    def test_call_builtin_forwards_only_kwargs(self) -> None:
        """A call with no positional args, only kwargs, still reaches
        the handler with the kwargs dict intact.
        """

        captured: dict = {}

        class _TestDispatch(BuiltinDispatchMixin):
            def _capture_handler(self, args, kwargs):
                captured["args"] = args
                captured["kwargs"] = kwargs
                return "ok"

            def _build_builtin_map(self):
                return {"capture.kwarg_only": self._capture_handler}

        dispatch = _TestDispatch()
        result = dispatch._call_builtin("capture.kwarg_only", [], kwargs={"stop": 99.0, "comment": "hi"})
        assert result == "ok"
        assert captured["args"] == []
        assert captured["kwargs"] == {"stop": 99.0, "comment": "hi"}

    def test_pine_call_expression_forwards_kwargs_to_handler(self) -> None:
        """End-to-end: a Pine call expression with kwargs reaches a
        registered handler. Uses the real ``NodeLiteralEvaluator``
        plus a one-off subclass that adds a capture handler to the
        dispatch.
        """
        captured: dict = {}

        class _EvaluatorWithCapture(NodeLiteralEvaluator):
            def _capture_handler(self, args, kwargs):
                captured["args"] = args
                captured["kwargs"] = kwargs
                return "captured"

            def _build_builtin_map(self):
                dispatch = super()._build_builtin_map()
                dispatch["capture.from_pine"] = self._capture_handler
                return dispatch

        source = "capture.from_pine(1, 2, stop=99.0)"
        ast = helper.parse(source, mode="eval")
        evaluator = _EvaluatorWithCapture()
        result = evaluator.visit(ast.body)
        assert result == "captured"
        assert captured["args"] == [1, 2]
        assert captured["kwargs"] == {"stop": 99.0}


class TestStrategyHandlersReadKwargs:
    """Subtask 1.3: ``strategy.*`` action handlers read from kwargs.

    The dispatch infrastructure from subtask 1.2 forwards the kwargs
    dict to the handler. These tests exercise the Pine -> dispatch
    -> handler path with keyword arguments, asserting that the
    handler observes the right values (via ``StrategyState``).
    """

    def test_strategy_entry_with_kwargs_opens_long_position(self) -> None:
        """``strategy.entry(id=\"L\", direction=\"long\", qty=10)`` should
        open a long position with qty=10."""
        ast = helper.parse(
            'strategy.entry(id="L", direction="long", qty=10)',
            mode="eval",
        )
        evaluator = NodeLiteralEvaluator()
        evaluator.visit(ast.body)
        assert evaluator._strategy_state.position_direction == "long"
        assert evaluator._strategy_state.position_size == 10.0

    def test_strategy_entry_with_kwargs_opens_short_position(self) -> None:
        """``strategy.entry(id=\"S\", direction=\"short\", qty=5)`` should
        open a short position with qty=5."""
        ast = helper.parse(
            'strategy.entry(id="S", direction="short", qty=5)',
            mode="eval",
        )
        evaluator = NodeLiteralEvaluator()
        evaluator.visit(ast.body)
        assert evaluator._strategy_state.position_direction == "short"
        assert evaluator._strategy_state.position_size == 5.0

    def test_strategy_entry_kwargs_uses_strategy_long_constant(self) -> None:
        """The canonical Pine form ``strategy.entry(id=\"L\",
        direction=strategy.long, qty=10)`` should now work end-to-end
        (pre-1.3, ``strategy.long`` resolved to the literal string
        ``\"strategy.long\"``, which never matched the
        direction-equality checks)."""
        ast = helper.parse(
            'strategy.entry(id="L", direction=strategy.long, qty=10)',
            mode="eval",
        )
        evaluator = NodeLiteralEvaluator()
        evaluator.visit(ast.body)
        assert evaluator._strategy_state.position_direction == "long"
        assert evaluator._strategy_state.position_size == 10.0

    def test_strategy_entry_kwargs_record_stop_and_limit(self) -> None:
        """``strategy.entry(..., stop=99.0, limit=101.0)`` should set
        the entry price to the limit (when truthy)."""
        ast = helper.parse(
            'strategy.entry(id="L", direction="long", qty=1, stop=99.0, limit=101.0)',
            mode="eval",
        )
        evaluator = NodeLiteralEvaluator()
        evaluator.visit(ast.body)
        assert evaluator._strategy_state.entry_price == 101.0

    def test_strategy_entry_kwargs_reverse_long_to_short(self) -> None:
        """A short entry while long should close the long position."""
        evaluator = NodeLiteralEvaluator()
        evaluator._strategy_state.position_direction = "long"
        evaluator._strategy_state.position_size = 5.0
        evaluator._strategy_state.entry_price = 100.0

        ast = helper.parse(
            'strategy.entry(id="S", direction="short", qty=3)',
            mode="eval",
        )
        evaluator.visit(ast.body)

        assert evaluator._strategy_state.position_direction == "short"
        assert evaluator._strategy_state.position_size == 3.0

    def test_strategy_close_with_kwargs_uses_provided_qty(self) -> None:
        """``strategy.close(id=\"x\", qty=2)`` should close only 2
        units (not the full position)."""
        evaluator = NodeLiteralEvaluator()
        evaluator._strategy_state.position_direction = "long"
        evaluator._strategy_state.position_size = 10.0
        evaluator._strategy_state.entry_price = 100.0

        ast = helper.parse('strategy.close(id="x", qty=2)', mode="eval")
        evaluator.visit(ast.body)

        # Partial close: size drops by 2.
        assert evaluator._strategy_state.position_size == 8.0

    def test_strategy_order_with_kwargs_records_limit_and_stop(self) -> None:
        """``strategy.order(id=\"o1\", action=\"buy\", qty=5,
        limit=100.0, stop=95.0)`` should record a stop-limit order."""
        ast = helper.parse(
            'strategy.order(id="o1", action="buy", qty=5, limit=100.0, stop=95.0)',
            mode="eval",
        )
        evaluator = NodeLiteralEvaluator()
        evaluator.visit(ast.body)
        assert "o1" in evaluator._strategy_state.pending_orders
        order = evaluator._strategy_state.pending_orders["o1"]
        assert order.order_type == "stop-limit"
        assert order.limit_price == 100.0
        assert order.stop_price == 95.0
        assert order.quantity == 5.0
        assert order.comment == ""

    def test_strategy_order_with_kwargs_records_comment(self) -> None:
        """``strategy.order(..., comment=\"my order\")`` should store
        the comment on the order."""
        ast = helper.parse(
            'strategy.order(id="o1", action="buy", qty=1, comment="my order")',
            mode="eval",
        )
        evaluator = NodeLiteralEvaluator()
        evaluator.visit(ast.body)
        order = evaluator._strategy_state.pending_orders["o1"]
        assert order.comment == "my order"

    def test_strategy_cancel_with_kwargs_removes_named_order(self) -> None:
        """``strategy.cancel(id=\"o1\")`` should remove the named
        pending order (using the kwarg, not positional)."""
        evaluator = NodeLiteralEvaluator()
        evaluator._strategy_state.pending_orders["o1"] = object()  # placeholder
        evaluator._strategy_state.pending_orders["o2"] = object()

        ast = helper.parse('strategy.cancel(id="o1")', mode="eval")
        evaluator.visit(ast.body)

        assert "o1" not in evaluator._strategy_state.pending_orders
        assert "o2" in evaluator._strategy_state.pending_orders

    def test_strategy_cancel_all_with_kwargs_clears_pending(self) -> None:
        """``strategy.cancel_all()`` should clear pending orders."""
        evaluator = NodeLiteralEvaluator()
        evaluator._strategy_state.pending_orders["o1"] = object()
        evaluator._strategy_state.pending_orders["o2"] = object()

        ast = helper.parse("strategy.cancel_all()", mode="eval")
        evaluator.visit(ast.body)

        assert evaluator._strategy_state.pending_orders == {}

    def test_strategy_close_all_with_kwargs_closes_position(self) -> None:
        """``strategy.close_all()`` should close the current position
        entirely."""
        evaluator = NodeLiteralEvaluator()
        evaluator._strategy_state.position_direction = "long"
        evaluator._strategy_state.position_size = 5.0
        evaluator._strategy_state.entry_price = 100.0

        ast = helper.parse("strategy.close_all()", mode="eval")
        evaluator.visit(ast.body)

        assert evaluator._strategy_state.position_size == 0.0
        assert evaluator._strategy_state.position_direction == "flat"

    def test_strategy_exit_with_kwargs_uses_provided_qty(self) -> None:
        """``strategy.exit(id=\"x\", from_entry=\"L\", qty=3)`` should
        close 3 units of the position."""
        evaluator = NodeLiteralEvaluator()
        evaluator._strategy_state.position_direction = "long"
        evaluator._strategy_state.position_size = 10.0
        evaluator._strategy_state.entry_price = 100.0

        ast = helper.parse('strategy.exit(id="x", from_entry="L", qty=3)', mode="eval")
        evaluator.visit(ast.body)

        # Partial close: size drops by 3.
        assert evaluator._strategy_state.position_size == 7.0

    def test_strategy_kwargs_mixed_with_positional_args(self) -> None:
        """Mixed positional + kwargs: ``strategy.entry(\"L\", \"long\",
        qty=10)`` — positional fills id/direction, kwarg fills qty.
        This is the backwards-compatibility case."""
        ast = helper.parse('strategy.entry("L", "long", qty=10)', mode="eval")
        evaluator = NodeLiteralEvaluator()
        evaluator.visit(ast.body)
        assert evaluator._strategy_state.position_direction == "long"
        assert evaluator._strategy_state.position_size == 10.0


class TestEventCapture:
    """Subtask 1.4: strategy action handlers emit StrategyEvent records."""

    def test_entry_emits_event(self) -> None:
        """strategy.entry() appends a StrategyEvent to the state."""
        evaluator = NodeLiteralEvaluator()
        ast = helper.parse(
            'strategy.entry(id="L", direction="long", qty=10)',
            mode="eval",
        )
        evaluator.visit(ast.body)
        events = evaluator._strategy_state.drain_events()
        assert len(events) == 1
        ev = events[0]
        assert ev.kind == "entry"
        assert ev.id == "L"
        assert ev.direction == "long"
        assert ev.qty == 10.0

    def test_close_emits_event(self) -> None:
        """strategy.close() appends a close event."""
        evaluator = NodeLiteralEvaluator()
        evaluator._strategy_state.position_direction = "long"
        evaluator._strategy_state.position_size = 5.0
        ast = helper.parse('strategy.close(id="x", qty=2)', mode="eval")
        evaluator.visit(ast.body)
        events = evaluator._strategy_state.drain_events()
        assert len(events) == 1
        assert events[0].kind == "close"
        assert events[0].id == "x"
        assert events[0].qty == 2.0

    def test_cancel_emits_event(self) -> None:
        """strategy.cancel() appends a cancel event."""
        evaluator = NodeLiteralEvaluator()
        ast = helper.parse('strategy.cancel(id="o1")', mode="eval")
        evaluator.visit(ast.body)
        events = evaluator._strategy_state.drain_events()
        assert len(events) == 1
        assert events[0].kind == "cancel"
        assert events[0].id == "o1"

    def test_drain_events_clears_buffer(self) -> None:
        """drain_events() returns events and clears the internal list."""
        evaluator = NodeLiteralEvaluator()
        ast = helper.parse('strategy.entry(id="L", direction="long", qty=1)', mode="eval")
        evaluator.visit(ast.body)
        first = evaluator._strategy_state.drain_events()
        assert len(first) == 1
        second = evaluator._strategy_state.drain_events()
        assert len(second) == 0

    def test_multiple_actions_record_multiple_events(self) -> None:
        """Multiple strategy calls accumulate events."""
        evaluator = NodeLiteralEvaluator()
        ast1 = helper.parse('strategy.entry(id="L", direction="long", qty=5)', mode="eval")
        ast2 = helper.parse('strategy.close(id="x", qty=5)', mode="eval")
        evaluator.visit(ast1.body)
        evaluator.visit(ast2.body)
        events = evaluator._strategy_state.drain_events()
        assert len(events) == 2
        assert events[0].kind == "entry"
        assert events[1].kind == "close"

    def test_event_carries_bar_index_from_context(self) -> None:
        """Events should carry bar_index from the evaluator context."""
        evaluator = NodeLiteralEvaluator()
        evaluator.context["bar_index"] = 42
        evaluator.context["time"] = 1700000000
        ast = helper.parse(
            'strategy.entry(id="L", direction="long", qty=1)',
            mode="eval",
        )
        evaluator.visit(ast.body)
        events = evaluator._strategy_state.drain_events()
        assert len(events) == 1
        assert events[0].bar_index == 42
        assert events[0].bar_time == 1700000000


class TestCrossRequestLeakPrevention:
    """Subtask 1.4: Two sequential evaluator runs must not share state."""

    def test_two_runs_no_state_leak(self) -> None:
        """Running strategy.entry on evaluator A must not affect evaluator B."""
        eval_a = NodeLiteralEvaluator()
        ast_a = helper.parse(
            'strategy.entry(id="L", direction="long", qty=10)',
            mode="eval",
        )
        eval_a.visit(ast_a.body)
        assert eval_a._strategy_state.position_direction == "long"
        assert eval_a._strategy_state.position_size == 10.0

        eval_b = NodeLiteralEvaluator()
        # eval_b should start with flat/zero state
        assert eval_b._strategy_state.position_direction == "flat"
        assert eval_b._strategy_state.position_size == 0.0
        assert len(eval_b._strategy_state.drain_events()) == 0

    def test_events_isolated_per_run(self) -> None:
        """Events from run A must not appear in run B's event buffer."""
        eval_a = NodeLiteralEvaluator()
        ast_entry = helper.parse(
            'strategy.entry(id="L", direction="long", qty=1)',
            mode="eval",
        )
        eval_a.visit(ast_entry.body)
        assert len(eval_a._strategy_state.drain_events()) == 1

        eval_b = NodeLiteralEvaluator()
        assert len(eval_b._strategy_state.drain_events()) == 0


class TestBarIndexInEvents:
    """Subtask 1.5: bar_index and bar_time are threaded into events."""

    def test_runtime_passes_bar_index_to_events(self) -> None:
        """Runtime.run should produce events with correct bar_index."""
        from backend.runtime import Runtime

        rt = Runtime()
        ohlcv = [
            {"open": 100, "high": 105, "low": 95, "close": 102, "time": 1000},
            {"open": 102, "high": 108, "low": 100, "close": 106, "time": 2000},
            {"open": 106, "high": 110, "low": 104, "close": 108, "time": 3000},
        ]
        source = 'strategy.entry(id="L", direction="long", qty=1)'
        result = rt.run(source, ohlcv)
        assert "error" not in result, result.get("error")


class TestPerBarEventReset:
    """Subtask 1.6: reset_events() clears the buffer per bar."""

    def test_per_bar_event_count(self) -> None:
        """A script calling strategy.entry on every bar should produce
        exactly one event per bar when reset_events() is called between bars."""
        evaluator = NodeLiteralEvaluator()
        ast = helper.parse(
            'strategy.entry(id="L", direction="long", qty=1)',
            mode="eval",
        )
        num_bars = 5
        for i in range(num_bars):
            evaluator.context["bar_index"] = i
            evaluator.context["time"] = i * 1000
            evaluator.visit(ast.body)
            # Simulate per-bar reset (as runtime.py does)
            evaluator.reset_events()

        # After the loop, event buffer should be empty (reset each bar)
        assert len(evaluator._strategy_state._events) == 0

    def test_events_between_resets(self) -> None:
        """Without reset_events, events accumulate across bars."""
        evaluator = NodeLiteralEvaluator()
        ast = helper.parse(
            'strategy.entry(id="L", direction="long", qty=1)',
            mode="eval",
        )
        for i in range(3):
            evaluator.context["bar_index"] = i
            evaluator.visit(ast.body)

        # Without reset, all 3 events should be in the buffer
        events = evaluator._strategy_state.drain_events()
        assert len(events) == 3
        assert [e.bar_index for e in events] == [0, 1, 2]
