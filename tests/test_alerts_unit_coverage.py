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

"""Unit coverage for alert helpers and once_per_bar_close gating."""

from __future__ import annotations

from types import SimpleNamespace

from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.evaluator.builtins.alerts import FREQ_ALL
from pynescript.ast.evaluator.builtins.alerts import FREQ_ONCE_PER_BAR
from pynescript.ast.evaluator.builtins.alerts import FREQ_ONCE_PER_BAR_CLOSE
from pynescript.ast.evaluator.builtins.alerts import AlertCondition
from pynescript.ast.evaluator.builtins.alerts import AlertEvent
from pynescript.ast.evaluator.builtins.alerts import export_alerts_from_evaluator
from pynescript.ast.evaluator.builtins.alerts import normalize_alert_freq
from pynescript.runtime import Runtime


def _bars(n: int = 3) -> list[dict[str, float | int]]:
    return [
        {
            "time": 1_700_000_000_000 + i * 60_000,
            "open": 100.0 + i,
            "high": 101.0 + i,
            "low": 99.0 + i,
            "close": 100.5 + i,
            "volume": 10.0 + i,
        }
        for i in range(n)
    ]


class TestNormalizeAlertFreq:
    def test_aliases_and_defaults(self) -> None:
        assert normalize_alert_freq(None) == FREQ_ONCE_PER_BAR
        assert normalize_alert_freq("") == FREQ_ONCE_PER_BAR
        assert normalize_alert_freq("  ") == FREQ_ONCE_PER_BAR
        assert normalize_alert_freq("once_per_bar") == FREQ_ONCE_PER_BAR
        assert normalize_alert_freq("freq_once_per_bar") == FREQ_ONCE_PER_BAR
        assert normalize_alert_freq("alert.freq_once_per_bar") == FREQ_ONCE_PER_BAR
        assert normalize_alert_freq("once_per_bar_close") == FREQ_ONCE_PER_BAR_CLOSE
        assert normalize_alert_freq("freq_once_per_bar_close") == FREQ_ONCE_PER_BAR_CLOSE
        assert normalize_alert_freq("alert.freq_once_per_bar_close") == FREQ_ONCE_PER_BAR_CLOSE
        assert normalize_alert_freq("all") == FREQ_ALL
        assert normalize_alert_freq("freq_all") == FREQ_ALL
        assert normalize_alert_freq("alert.freq_all") == FREQ_ALL
        assert normalize_alert_freq("  ALL ") == FREQ_ALL
        assert normalize_alert_freq("custom_token") == "custom_token"


class TestAlertEventToDict:
    def test_drops_empty_title(self) -> None:
        d = AlertEvent(message="m", freq=FREQ_ALL, title="").to_dict()
        assert "title" not in d
        assert d["message"] == "m"
        assert d["freq"] == FREQ_ALL
        assert d["source"] == "alert"

    def test_keeps_nonempty_title(self) -> None:
        d = AlertEvent(
            message="m",
            freq=FREQ_ONCE_PER_BAR,
            bar_index=2,
            time=99,
            title="T",
            source="alertcondition",
        ).to_dict()
        assert d["title"] == "T"
        assert d["bar_index"] == 2
        assert d["time"] == 99
        assert d["source"] == "alertcondition"

    def test_alertcondition_to_dict(self) -> None:
        c = AlertCondition(condition=True, title="t", message="m", bar_index=1, time=2)
        assert c.to_dict() == {
            "condition": True,
            "title": "t",
            "message": "m",
            "bar_index": 1,
            "time": 2,
        }


class TestExportAlertsFromEvaluator:
    def test_none_and_empty(self) -> None:
        assert export_alerts_from_evaluator(None) == []
        assert export_alerts_from_evaluator(SimpleNamespace()) == []
        assert export_alerts_from_evaluator(SimpleNamespace(export_alerts=lambda: [])) == []

    def test_export_alerts_raises(self) -> None:
        class Boom:
            def export_alerts(self) -> list:
                raise RuntimeError("boom")

        assert export_alerts_from_evaluator(Boom()) == []

    def test_get_triggered_alerts_callable(self) -> None:
        ev = AlertEvent(message="x", freq=FREQ_ALL, title=None)

        class Host:
            def get_triggered_alerts(self) -> list[AlertEvent]:
                return [ev]

        out = export_alerts_from_evaluator(Host())
        assert out == [ev.to_dict()]

    def test_get_triggered_alerts_raises(self) -> None:
        class Boom:
            def get_triggered_alerts(self) -> list:
                raise RuntimeError("x")

        assert export_alerts_from_evaluator(Boom()) == []

    def test_raw_list_mixed_shapes(self) -> None:
        class Blob:
            message = "blob"
            freq = FREQ_ALL
            bar_index = 3
            time = 4
            source = "alert"

        host = SimpleNamespace(
            _triggered_alerts=[
                AlertEvent(message="a", freq=FREQ_ALL, title=""),
                {"message": "b", "freq": "all", "source": "alert"},
                Blob(),
            ]
        )
        out = export_alerts_from_evaluator(host)
        assert out[0]["message"] == "a"
        assert "title" not in out[0]
        assert out[1]["message"] == "b"
        assert out[2]["message"] == "blob"
        assert out[2]["bar_index"] == 3


class TestOncePerBarCloseEvaluator:
    def test_skips_when_unconfirmed_object(self) -> None:
        ctx = {"bar_index": 5, "time": 100, "barstate": SimpleNamespace(isconfirmed=False)}
        ev = NodeLiteralEvaluator(context=ctx)
        ev.evaluate_script('alert("x", alert.freq_once_per_bar_close)')
        assert ev.export_alerts() == []

    def test_fires_when_confirmed_object(self) -> None:
        ctx = {"bar_index": 5, "time": 100, "barstate": SimpleNamespace(isconfirmed=True)}
        ev = NodeLiteralEvaluator(context=ctx)
        ev.evaluate_script('alert("y", alert.freq_once_per_bar_close)')
        alerts = ev.export_alerts()
        assert len(alerts) == 1
        assert alerts[0]["freq"] == FREQ_ONCE_PER_BAR_CLOSE
        assert alerts[0]["message"] == "y"

    def test_flat_barstate_isconfirmed_false(self) -> None:
        ctx = {"bar_index": 1, "barstate.isconfirmed": False}
        ev = NodeLiteralEvaluator(context=ctx)
        ev.evaluate_script('alert("z", "once_per_bar_close")')
        assert ev.export_alerts() == []

    def test_dict_barstate_islast_fallback(self) -> None:
        ctx = {"bar_index": 2, "time": 50, "barstate": {"islast": True}}
        ev = NodeLiteralEvaluator(context=ctx)
        ev.evaluate_script('alert("last", "freq_once_per_bar_close")')
        assert len(ev.export_alerts()) == 1

    def test_zero_arg_alert_noop(self) -> None:
        ev = NodeLiteralEvaluator(context={"bar_index": 0})
        ev.evaluate_script("alert()")
        assert ev.export_alerts() == []

    def test_freq_all_repeats_same_bar(self) -> None:
        ev = NodeLiteralEvaluator(context={"bar_index": 7, "time": 1})
        ev.evaluate_script('alert("a", alert.freq_all)\nalert("a", alert.freq_all)')
        assert len(ev.get_triggered_alerts()) == 2

    def test_export_alert_conditions(self) -> None:
        ev = NodeLiteralEvaluator(context={"bar_index": 1, "time": 9})
        ev.evaluate_script('alertcondition(true, "Title", "Msg")')
        conds = ev.export_alert_conditions()
        assert conds[0]["condition"] is True
        assert conds[0]["title"] == "Title"
        fired = export_alerts_from_evaluator(ev)
        assert fired and fired[0]["source"] == "alertcondition"


class TestRuntimeAlertExport:
    def test_interpret_exports_freq_variants(self) -> None:
        src = """//@version=5
indicator("al")
alert("hi", alert.freq_all)
alert("close", alert.freq_once_per_bar_close)
alert("once", alert.freq_once_per_bar)
plot(1)
"""
        out = Runtime(symbol="AL").run(src, _bars(3), mode="interpret")
        assert "error" not in out, out.get("error")
        alerts = out.get("alerts") or []
        msgs = {a["message"] for a in alerts}
        assert {"hi", "close", "once"} <= msgs
        freqs = {a["freq"] for a in alerts}
        assert FREQ_ALL in freqs
        assert FREQ_ONCE_PER_BAR_CLOSE in freqs
        assert FREQ_ONCE_PER_BAR in freqs
        # once_per_bar dedups within a bar; freq_all fires every call/bar
        assert sum(1 for a in alerts if a["message"] == "hi") == 3
        assert sum(1 for a in alerts if a["message"] == "once") == 3
