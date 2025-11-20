# Copyright 2024-2025 jango_blockchained
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

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yfinance as yf


ticker = "TSLA"
filename = "tsla.csv"


def download_data():
    tsla = yf.Ticker(ticker)
    hist = tsla.history(period="max", interval="1d")
    hist.to_csv(filename)


def read_data():
    hist = None
    if Path(filename).exists():
        hist = pd.read_csv(filename, index_col=0, parse_dates=True)
    return hist


hist = read_data()


if __name__ == "__main__":
    download_data()
