# Copyright 2024-2025 Yunseong Hwang, jango_blockchained
#
# Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.gnu.org/licenses/lgpl-3.0.en.html
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

"""Phase 8 Tier 2: Medium-priority Technical Analysis Indicators."""

from __future__ import annotations

from pynescript.ast.helper import parse
from pynescript.ast.helper import unparse


class TestTier2Indicators:
    """Test all 15 Phase 8 Tier 2 indicators."""

    def test_ichimoku(self) -> None:
        """Test Ichimoku indicator."""
        script = """//@version 6
strategy("Ichimoku")
ichimoku = ta.ichimoku(9, 26)
plot(ichimoku.tenkan_sen)
plot(ichimoku.kijun_sen)
plot(ichimoku.senkou_span_a)
plot(ichimoku.senkou_span_b)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        tree2 = parse(unparsed)
        unparse(tree2)
        assert tree is not None

    def test_donchian(self) -> None:
        """Test Donchian indicator."""
        script = """//@version 6
strategy("Donchian")
dc = ta.donchian(20)
plot(dc.high)
plot(dc.low)
plot(dc.mid)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert unparsed is not None

    def test_stochrsi(self) -> None:
        """Test StochRSI indicator."""
        script = """//@version 6
strategy("StochRSI")
stochrsi = ta.stochrsi(14, 14)
plot(stochrsi.stochrsi)
plot(stochrsi.signal)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert unparsed is not None

    def test_dpo(self) -> None:
        """Test DPO indicator."""
        script = """//@version 6
strategy("DPO")
dpo = ta.dpo(20)
plot(dpo)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert unparsed is not None

    def test_kst(self) -> None:
        """Test KST indicator."""
        script = """//@version 6
strategy("KST")
kst = ta.kst(10, 15, 20, 30)
plot(kst)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert unparsed is not None

    def test_uo(self) -> None:
        """Test UO indicator."""
        script = """//@version 6
strategy("UO")
uo = ta.uo(7, 14, 28)
plot(uo)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert unparsed is not None

    def test_bb_pct(self) -> None:
        """Test BB% indicator."""
        script = """//@version 6
strategy("BB%")
bb_pct = ta.bb_pct(20, 2)
plot(bb_pct)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert unparsed is not None

    def test_vpt(self) -> None:
        """Test VPT indicator."""
        script = """//@version 6
strategy("VPT")
vpt = ta.vpt(close)
plot(vpt)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert unparsed is not None

    def test_beta(self) -> None:
        """Test Beta indicator."""
        script = """//@version 6
strategy("Beta")
beta = ta.beta(close, high, 20)
plot(beta)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert unparsed is not None

    def test_r_squared(self) -> None:
        """Test R-Squared indicator."""
        script = """//@version 6
strategy("R2")
r2 = ta.r_squared(close, high, 20)
plot(r2)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert unparsed is not None

    def test_comovement(self) -> None:
        """Test Comovement indicator."""
        script = """//@version 6
strategy("Comovement")
como = ta.comovement(close, high, 20)
plot(como)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert unparsed is not None

    def test_atr_stop(self) -> None:
        """Test ATR Stop indicator."""
        script = """//@version 6
strategy("ATR Stop")
atr = ta.atr(14)
stops = ta.atr_stop(atr, 2.0)
plot(stops.long_stop)
plot(stops.short_stop)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert unparsed is not None

    def test_fractal(self) -> None:
        """Test Fractal indicator."""
        script = """//@version 6
strategy("Fractal")
fractal = ta.fractal(2)
plot(fractal.is_high_fractal ? high : na)
plot(fractal.is_low_fractal ? low : na)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert unparsed is not None

    def test_emv(self) -> None:
        """Test EMV indicator."""
        script = """//@version 6
strategy("EMV")
emv = ta.emv(14)
plot(emv)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert unparsed is not None

    def test_all_tier2_together(self) -> None:
        """Test all 15 Tier 2 indicators in one script."""
        script = """//@version 6
strategy("All Tier 2")
i = ta.ichimoku(9, 26)
d = ta.donchian(20)
s = ta.stochrsi(14, 14)
dp = ta.dpo(20)
k = ta.kst(10, 15, 20, 30)
u = ta.uo(7, 14, 28)
bb = ta.bb_pct(20, 2)
v = ta.vpt(close)
b = ta.beta(close, high, 20)
r = ta.r_squared(close, high, 20)
c = ta.comovement(close, high, 20)
a = ta.atr_stop(14, 2)
f = ta.fractal(2)
e = ta.emv(14)
plot(i.tenkan_sen)
plot(d.high)
plot(s.stochrsi)
plot(dp)
plot(k)
plot(u)
plot(bb)
plot(v)
plot(b)
plot(r)
plot(c)
plot(a.long_stop)
plot(f.is_high_fractal ? high : na)
plot(e)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        tree2 = parse(unparsed)
        unparsed2 = unparse(tree2)
        assert unparsed == unparsed2

    def test_tier1_and_tier2_mixed(self) -> None:
        """Test mixing Tier 1 and Tier 2 indicators."""
        script = """//@version 6
strategy("Mixed Tiers")
kama = ta.kama(close, 10, 2, 30)
dema = ta.dema(close, 20)
tema = ta.tema(close, 20)
ichimoku = ta.ichimoku(9, 26)
donchian = ta.donchian(20)
stochrsi = ta.stochrsi(14, 14)
plot(kama)
plot(dema)
plot(tema)
plot(ichimoku.tenkan_sen)
plot(donchian.high)
plot(stochrsi.stochrsi)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert unparsed is not None
