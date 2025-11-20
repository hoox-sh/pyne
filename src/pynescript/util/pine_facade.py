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

"""TradingView Pine Script Facade - Download Built-in Scripts.

Provides utilities to fetch Pine Script code and documentation from TradingView.
Includes thread-safe HTTP session management and progress tracking.
"""

from __future__ import annotations

import pathlib
import threading

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
from typing import Any
from urllib.parse import quote

import requests  # type: ignore[import-untyped]
import tqdm  # type: ignore[import-untyped]


_THREAD_LOCAL = threading.local()
_THREAD_SESSIONS: set[requests.Session] = set()
_THREAD_SESSIONS_LOCK = threading.Lock()


def _register_thread_session(session: requests.Session) -> requests.Session:
    """Register a session for cleanup on thread exit.
    
    Args:
        session: The requests.Session to register
        
    Returns:
        The session passed in (for chaining)
    """
    with _THREAD_SESSIONS_LOCK:
        _THREAD_SESSIONS.add(session)
    return session


def _get_thread_session() -> requests.Session:
    session = getattr(_THREAD_LOCAL, "session", None)
    if session is None:
        session = _register_thread_session(requests.Session())
        _THREAD_LOCAL.session = session
    return session


def _close_thread_sessions() -> None:
    with _THREAD_SESSIONS_LOCK:
        sessions = list(_THREAD_SESSIONS)
        _THREAD_SESSIONS.clear()
    for session in sessions:
        session.close()


def _normalize_filename(script_name: str, mapping: dict[str, str]) -> str:
    script_name_prefix = script_name.lower()
    for from_pattern, replace_to in mapping.items():
        script_name_prefix = script_name_prefix.replace(from_pattern, replace_to)
    return f"{script_name_prefix}.pine"


def _session_provider_factory(base_session: requests.Session) -> Callable[[], requests.Session]:
    def _provider() -> requests.Session:
        return base_session

    return _provider


def _download_script(
    script_meta: dict[str, Any],
    script_dir: pathlib.Path,
    encoding: str,
    mapping: dict[str, str],
    session_provider: Callable[[], requests.Session],
) -> str:
    script_name = str(script_meta["scriptName"])
    script_id_part = script_meta["scriptIdPart"]
    script_version = script_meta["version"]

    session = session_provider()
    script = get_script(script_id_part, script_version, session=session)
    script_source = script["source"]

    script_filename = _normalize_filename(script_name, mapping)

    with open(script_dir / script_filename, "w", encoding=encoding) as f:
        f.write(script_source)

    return script_name


def list_builtin_scripts(session: requests.Session | None = None):
    url = "https://pine-facade.tradingview.com"
    path = "/pine-facade/list/"
    params = {"filter": "template"}
    requester = session or requests
    response = requester.get(url + path, params=params, timeout=60)
    response.raise_for_status()
    result = response.json()
    return result


def get_script(script_id_part, version, session: requests.Session | None = None):
    url = "https://pine-facade.tradingview.com"
    path = f"/pine-facade/get/{quote(script_id_part)}/{version}"
    params = {"no_4xx": "false"}
    requester = session or requests
    response = requester.get(url + path, params=params, timeout=60)
    response.raise_for_status()
    result = response.json()
    return result


def download_builtin_scripts(script_dir, encoding=None, max_workers: int | None = None):
    script_dir = pathlib.Path(script_dir)

    encoding = encoding or "utf-8"

    if not script_dir.exists():
        script_dir.mkdir(parents=True, exist_ok=True)

    script_name_replace_mapping = {
        " ": "_",
        "-": "_",
        "/": "_",
    }

    with requests.Session() as listing_session:
        script_list = list_builtin_scripts(session=listing_session)

    if not script_list:
        return

    total_scripts = len(script_list)
    worker_count = max_workers or min(8, total_scripts)
    worker_count = max(1, worker_count)

    with tqdm.tqdm(total=total_scripts, desc="Downloading scripts", unit="script") as progress_bar:
        if worker_count == 1:
            with requests.Session() as session:
                session_provider = _session_provider_factory(session)
                for script_meta in script_list:
                    script_name = _download_script(
                        script_meta,
                        script_dir,
                        encoding,
                        script_name_replace_mapping,
                        session_provider,
                    )
                    progress_bar.set_postfix_str(script_name, refresh=False)
                    progress_bar.update(1)
            return

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [
                executor.submit(
                    _download_script,
                    script_meta,
                    script_dir,
                    encoding,
                    script_name_replace_mapping,
                    _get_thread_session,
                )
                for script_meta in script_list
            ]
            try:
                for future in as_completed(futures):
                    script_name = future.result()
                    progress_bar.set_postfix_str(script_name, refresh=False)
                    progress_bar.update(1)
            except Exception:
                for future in futures:
                    future.cancel()
                raise
            finally:
                _close_thread_sessions()
