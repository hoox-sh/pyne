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

"""Coverage for backend.middleware.schemas validate() and schema dicts."""

from __future__ import annotations

import pytest

from backend.app import app
from backend.middleware import schemas as S


@pytest.fixture
def ctx():
    with app.test_request_context():
        yield


def _err_code(err: tuple | None) -> str | None:
    if err is None:
        return None
    resp, status = err
    assert status == 400
    body = resp.get_json()
    assert body["status"] == "error"
    return body["code"]


def _err_message(err: tuple | None) -> str:
    assert err is not None
    return err[0].get_json()["message"]


class TestValidateCore:
    def test_non_object_body(self, ctx) -> None:
        data, err = S.validate([], S.RUN_SCHEMA)
        assert data is None
        assert _err_code(err) == "INVALID_BODY"

    def test_none_body(self, ctx) -> None:
        data, err = S.validate(None, S.RUN_SCHEMA)
        assert data is None
        assert _err_code(err) == "INVALID_BODY"

    def test_unknown_field(self, ctx) -> None:
        data, err = S.validate({"script": "x", "data": [], "nope": 1}, S.RUN_SCHEMA)
        assert data is None
        assert _err_code(err) == "UNKNOWN_FIELDS"
        assert "nope" in _err_message(err)

    def test_missing_required(self, ctx) -> None:
        data, err = S.validate({"script": "x"}, S.RUN_SCHEMA)
        assert data is None
        assert _err_code(err) == "MISSING_FIELD"
        assert "data" in _err_message(err)

    def test_wrong_type_string(self, ctx) -> None:
        data, err = S.validate({"script": 12, "data": []}, S.RUN_SCHEMA)
        assert data is None
        assert _err_code(err) == "INVALID_FIELD"
        assert "string" in _err_message(err)

    def test_wrong_type_list(self, ctx) -> None:
        data, err = S.validate({"script": "x", "data": "bars"}, S.RUN_SCHEMA)
        assert data is None
        assert _err_code(err) == "INVALID_FIELD"
        assert "list" in _err_message(err)

    def test_wrong_type_bool(self, ctx) -> None:
        data, err = S.validate(
            {"script": "x", "data": [], "profiler": "yes"},
            S.RUN_SCHEMA,
        )
        assert data is None
        assert _err_code(err) == "INVALID_FIELD"
        assert "boolean" in _err_message(err)

    def test_bool_rejected_as_int(self, ctx) -> None:
        data, err = S.validate(
            {"script": "x", "data": [], "from_bar": True},
            S.RUN_SCHEMA,
        )
        assert data is None
        assert _err_code(err) == "INVALID_FIELD"
        assert "integer" in _err_message(err)

    def test_bool_rejected_as_float(self, ctx) -> None:
        data, err = S.validate(
            {"script": "x", "data": [], "timeout_seconds": True},
            S.RUN_SCHEMA,
        )
        assert data is None
        assert _err_code(err) == "INVALID_FIELD"
        assert "number" in _err_message(err)

    def test_int_coerced_to_float(self, ctx) -> None:
        data, err = S.validate(
            {"script": "x", "data": [], "timeout_seconds": 5},
            S.RUN_SCHEMA,
        )
        assert err is None
        assert data is not None
        assert data["timeout_seconds"] == 5.0
        assert isinstance(data["timeout_seconds"], float)

    def test_optional_null_uses_default(self, ctx) -> None:
        data, err = S.validate(
            {"script": "x", "data": [], "symbol": None, "mode": None},
            S.RUN_SCHEMA,
        )
        assert err is None
        assert data is not None
        assert data["symbol"] == "CHART"
        assert data["mode"] == "auto"

    def test_defaults_applied(self, ctx) -> None:
        data, err = S.validate({"script": "s", "data": [{"t": 1}]}, S.RUN_SCHEMA)
        assert err is None
        assert data is not None
        assert data["symbol"] == "CHART"
        assert data["mode"] == "auto"
        assert data["inputs"] == {}
        assert data["profiler"] is False
        assert data["forward_alerts"] is True
        assert data["alert_last_bar"] is True
        assert data["alert_batch"] is True
        assert data["libraries"] == []
        assert data["timeout_seconds"] is None
        assert data["from_bar"] is None
        assert data["to_bar"] is None
        assert data["data_source"] == ""
        assert data["data_options"] == {}
        assert data["webhook_url"] == ""

    def test_required_null_still_invalid(self, ctx) -> None:
        # Required field present as null is type-checked, not defaulted.
        data, err = S.validate({"script": None, "data": []}, S.RUN_SCHEMA)
        assert data is None
        assert _err_code(err) == "INVALID_FIELD"


class TestRunAndBatchSchemas:
    def test_run_valid_full(self, ctx) -> None:
        body = {
            "script": "//@version=6\nindicator('a')\nplot(close)",
            "data": [{"time": 1, "close": 1}],
            "symbol": "BTC",
            "data_source": "mock",
            "data_options": {"seed": 1},
            "mode": "interpret",
            "inputs": {"Len": 14},
            "profiler": True,
            "webhook_url": "https://example.com/h",
            "forward_alerts": False,
            "alert_last_bar": False,
            "alert_batch": False,
            "libraries": [],
            "timeout_seconds": 1.5,
            "from_bar": -10,
            "to_bar": -1,
        }
        data, err = S.validate(body, S.RUN_SCHEMA)
        assert err is None
        assert data is not None
        assert data["symbol"] == "BTC"
        assert data["profiler"] is True
        assert data["from_bar"] == -10

    def test_run_batch_defaults_and_required(self, ctx) -> None:
        data, err = S.validate({"scripts": [{}], "data": []}, S.RUN_BATCH_SCHEMA)
        assert err is None
        assert data is not None
        assert data["mode"] == "auto"
        assert data["forward_alerts"] is True
        assert S.RUN_BATCH_MAX_SCRIPTS == 8

        missing, err2 = S.validate({"data": []}, S.RUN_BATCH_SCHEMA)
        assert missing is None
        assert _err_code(err2) == "MISSING_FIELD"


class TestSessionSchemas:
    def test_session_create(self, ctx) -> None:
        data, err = S.validate({"script": "s", "data": [1]}, S.SESSION_CREATE_SCHEMA)
        assert err is None
        assert data is not None
        assert data["mode"] == "interpret"
        assert data["libraries"] == []

    def test_session_tick(self, ctx) -> None:
        data, err = S.validate({"bar": {"close": 1}}, S.SESSION_TICK_SCHEMA)
        assert err is None
        assert data is not None
        assert data["delta"] is False
        bad, err2 = S.validate({"bar": []}, S.SESSION_TICK_SCHEMA)
        assert bad is None
        assert _err_code(err2) == "INVALID_FIELD"

    def test_session_append(self, ctx) -> None:
        data, err = S.validate({"bars": []}, S.SESSION_APPEND_SCHEMA)
        assert err is None
        assert data is not None
        assert data["realtime_ticks"] == 1
        bad, err2 = S.validate({"bars": [], "realtime_ticks": 1.5}, S.SESSION_APPEND_SCHEMA)
        assert bad is None
        assert _err_code(err2) == "INVALID_FIELD"


class TestDataSchemas:
    def test_series_provide(self, ctx) -> None:
        body = {
            "exchange": "binance",
            "symbol": "BTC/USDT",
            "interval": "1m",
            "bars": [],
        }
        data, err = S.validate(body, S.DATA_SERIES_PROVIDE_SCHEMA)
        assert err is None
        assert data is not None
        assert data["market"] == "spot"
        assert data["source"] == "axis-local"

    def test_series_fetch_defaults(self, ctx) -> None:
        body = {"exchange": "x", "symbol": "S", "interval": "1h"}
        data, err = S.validate(body, S.DATA_SERIES_FETCH_SCHEMA)
        assert err is None
        assert data is not None
        assert data["history_bars"] == 5000

    def test_data_session_create(self, ctx) -> None:
        body = {
            "exchange": "x",
            "symbol": "S",
            "interval": "5m",
            "script": "s",
        }
        data, err = S.validate(body, S.DATA_SESSION_CREATE_SCHEMA)
        assert err is None
        assert data is not None
        assert data["mode"] == "interpret"
        assert data["history_bars"] == 5000

    def test_data_session_tick(self, ctx) -> None:
        data, err = S.validate(
            {"exchange": "x", "symbol": "S", "delta": True},
            S.DATA_SESSION_TICK_SCHEMA,
        )
        assert err is None
        assert data is not None
        assert data["delta"] is True
        missing, err2 = S.validate({"exchange": "x"}, S.DATA_SESSION_TICK_SCHEMA)
        assert missing is None
        assert _err_code(err2) == "MISSING_FIELD"

    def test_wrong_dict_type(self, ctx) -> None:
        data, err = S.validate(
            {
                "exchange": "x",
                "symbol": "S",
                "interval": "1m",
                "bars": [],
                "source": {"not": "str"},
            },
            S.DATA_SERIES_PROVIDE_SCHEMA,
        )
        assert data is None
        assert _err_code(err) == "INVALID_FIELD"


class TestPreviewBacktestAuthOptimize:
    def test_preview_chart_defaults(self, ctx) -> None:
        data, err = S.validate({}, S.PREVIEW_CHART_SCHEMA)
        assert err is None
        assert data == {"script": "", "data": {}, "options": {}}

    def test_preview_indicator_defaults(self, ctx) -> None:
        data, err = S.validate({}, S.PREVIEW_INDICATOR_SCHEMA)
        assert err is None
        assert data == {"expression": "", "data": {}, "options": {}}

    def test_backtest_quick(self, ctx) -> None:
        data, err = S.validate({}, S.BACKTEST_QUICK_SCHEMA)
        assert err is None
        assert data is not None
        assert data["initial_capital"] == 10000.0
        assert data["mock_data"] is False
        assert data["mock_bars"] == 252
        # int capital coerces to float
        data2, err2 = S.validate({"initial_capital": 1000}, S.BACKTEST_QUICK_SCHEMA)
        assert err2 is None
        assert data2 is not None
        assert data2["initial_capital"] == 1000.0

    def test_create_and_validate_key(self, ctx) -> None:
        data, err = S.validate({}, S.CREATE_KEY_SCHEMA)
        assert err is None
        assert data == {"tier": "hobby"}
        data2, err2 = S.validate({"api_key": "k"}, S.VALIDATE_KEY_SCHEMA)
        assert err2 is None
        assert data2 == {"api_key": "k"}
        missing, err3 = S.validate({}, S.VALIDATE_KEY_SCHEMA)
        assert missing is None
        assert _err_code(err3) == "MISSING_FIELD"

    def test_optimize_schema(self, ctx) -> None:
        body = {
            "script": "s",
            "data": [],
            "space": {"params": []},
        }
        data, err = S.validate(body, S.OPTIMIZE_SCHEMA)
        assert err is None
        assert data is not None
        assert data["n_trials"] == 30
        assert data["sampler"] == "auto"
        assert data["objective"] == "composite"
        assert data["validation"] == {}
        assert data["min_trades"] == 5
        assert data["seed"] is None
        assert data["oos_every_trial"] is True
        assert data["fixed_inputs"] == {}
        assert data["libraries"] == []

        bad, err2 = S.validate(
            {"script": "s", "data": [], "space": [], "n_trials": True},
            S.OPTIMIZE_SCHEMA,
        )
        assert bad is None
        assert _err_code(err2) == "INVALID_FIELD"
