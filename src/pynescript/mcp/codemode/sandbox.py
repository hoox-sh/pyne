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

"""Code Mode sandbox boundary.

## What the boundary is

``execute`` and ``search`` run model-written JavaScript in a separate process
launched with bubblewrap (``bwrap``). The namespace is the security boundary:

* ``--unshare-all`` gives new user, pid, net, ipc, uts, and cgroup namespaces.
  There is no network route, not even loopback.
* ``--clearenv`` starts the child with no environment, then sets only PATH,
  HOME, TMPDIR, LANG, and NO_COLOR. No ``ADMIN_TOKEN``, no API keys.
* ``--ro-bind`` exposes only the JavaScript runtime, the harness, and the
  shared library directories. The repository, the home directory, and every
  ``.env`` file are simply absent.
* ``--tmpfs /tmp`` makes writes private and disposable.
* ``--die-with-parent`` and ``--new-session`` leave no orphan and no terminal.
* ``--cap-drop ALL`` drops capabilities inside the user namespace.

## What the boundary is not

* Not a V8 isolate. The harness uses ``node:vm`` for capability shaping (no
  ``process``, ``require``, or ``fetch``), but ``vm`` is not treated as the
  security boundary; the namespace carries the weight.
* Not a seccomp filter. The child can fork, but every reachable path is a
  read-only bind plus a private tmpfs, and it has no network or credentials.
* Not available without bubblewrap. ``execute`` then fails closed. Setting
  ``PYNE_MCP_CODE_MODE_SANDBOX=subprocess`` accepts a weaker, documented mode:
  a plain child process with a cleared environment and a throwaway cwd, but
  host filesystem reads are still possible. That is an operator decision.

## Trust direction

The parent never trusts the child. Every ``call`` is re-resolved, risk-checked,
and dispatched through ``dispatch.call_tool``. The child cannot widen its own
permissions by lying.
"""

from __future__ import annotations

import json
import os
import re
import selectors
import shutil
import subprocess
import tempfile
import time

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pynescript.mcp.codemode.bridge import Handlers
from pynescript.mcp.codemode.protocol import SandboxRequest
from pynescript.mcp.codemode.protocol import SandboxResult


STDERR_CAP = 4_000
MAX_PROTOCOL_BYTES = 1_000_000
LIB_DIRS = ("/usr/lib", "/usr/lib64", "/lib", "/lib64")
SANDBOX_ENV: dict[str, str] = {
    "PATH": "/usr/bin",
    "HOME": "/tmp",
    "TMPDIR": "/tmp",
    "LANG": "C.UTF-8",
    "NO_COLOR": "1",
}
_SECRET_RE = re.compile(
    r"(?i)\b(admin[_-]?token|api[_-]?key|secret|token|password|authorization)\b\s*[:=]\s*([^\s,;]+)"
)


@dataclass(frozen=True)
class SandboxPlan:
    """A concrete process launch plan."""

    kind: str
    cmd: list[str]
    cwd: str
    env: dict[str, str]
    cleanup_dir: str | None = None


@dataclass(frozen=True)
class PlanError:
    """A fail-closed decision: no process is spawned."""

    message: str


def harness_path() -> Path:
    return Path(__file__).with_name("harness.mjs")


def resolve_js_runtime(env: dict[str, str] | None = None) -> tuple[str | None, str | None]:
    """Return ``(realpath, None)`` or ``(None, error)`` for the JS runtime."""
    source = os.environ if env is None else env
    requested = (source.get("PYNE_MCP_CODE_MODE_JS") or "").strip()
    if requested:
        found = shutil.which(requested) or (requested if Path(requested).is_file() else None)
        if not found:
            return None, (
                f"PYNE_MCP_CODE_MODE_JS={requested!r} was not found. "
                "Install Node.js >= 18 or point the variable at the runtime binary."
            )
        return os.path.realpath(found), None
    for name in ("node", "bun"):
        found = shutil.which(name)
        if found:
            return os.path.realpath(found), None
    return None, (
        "Code Mode needs a JavaScript runtime with node:vm (Node.js >= 18, or Bun). "
        "Install nodejs, or set PYNE_MCP_CODE_MODE_JS to the runtime binary."
    )


def resolve_sandbox_kind(env: dict[str, str] | None = None) -> tuple[str | None, str | None]:
    """Return ``(kind, None)`` or ``(None, error)``. Default is fail closed."""
    source = os.environ if env is None else env
    requested = (source.get("PYNE_MCP_CODE_MODE_SANDBOX") or "").strip()
    if requested == "subprocess":
        return "subprocess", None
    bwrap = shutil.which("bwrap")
    if bwrap:
        return "bwrap", None
    if requested == "bwrap":
        return None, (
            "PYNE_MCP_CODE_MODE_SANDBOX=bwrap but bubblewrap is not installed. "
            "Install bwrap, or set PYNE_MCP_CODE_MODE_SANDBOX=subprocess to accept the "
            "weaker documented mode (host filesystem reads still possible)."
        )
    return None, (
        "Code Mode needs bubblewrap for a real sandbox and bwrap is not installed. "
        "Install bwrap, or set PYNE_MCP_CODE_MODE_SANDBOX=subprocess to accept a plain "
        "child process with a cleared environment but host filesystem reads still possible."
    )


def build_bwrap_plan(
    *,
    runtime: str,
    harness: Path,
    bwrap: str | None = None,
) -> SandboxPlan:
    """Build the bubblewrap launch plan. No host path is writable."""
    binary = bwrap or shutil.which("bwrap") or "bwrap"
    cmd = [
        binary,
        "--unshare-all",
        "--die-with-parent",
        "--new-session",
        "--cap-drop",
        "ALL",
        "--clearenv",
    ]
    for key, value in SANDBOX_ENV.items():
        cmd.extend(["--setenv", key, value])
    for directory in LIB_DIRS:
        if Path(directory).exists():
            cmd.extend(["--ro-bind", directory, directory])
    cmd.extend(
        [
            "--ro-bind",
            runtime,
            "/runtime",
            "--ro-bind",
            str(harness),
            "/harness.mjs",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--tmpfs",
            "/tmp",
            "--chdir",
            "/tmp",
            "/runtime",
            "/harness.mjs",
        ]
    )
    return SandboxPlan(kind="bwrap", cmd=cmd, cwd=tempfile.gettempdir(), env={})


def build_subprocess_plan(*, runtime: str, harness: Path) -> SandboxPlan:
    """Build the documented weaker plan: cleared env, throwaway cwd, no namespace."""
    directory = tempfile.mkdtemp(prefix="pyne-codemode-")
    return SandboxPlan(
        kind="subprocess",
        cmd=[runtime, str(harness)],
        cwd=directory,
        env=dict(SANDBOX_ENV),
        cleanup_dir=directory,
    )


def default_plan(env: dict[str, str] | None = None) -> SandboxPlan | PlanError:
    """Resolve runtime and boundary, then build the plan. Fail closed."""
    runtime, runtime_error = resolve_js_runtime(env)
    if runtime_error is not None or runtime is None:
        return PlanError(runtime_error or "JavaScript runtime not found")
    kind, kind_error = resolve_sandbox_kind(env)
    if kind_error is not None or kind is None:
        return PlanError(kind_error or "sandbox kind not resolved")
    harness = harness_path()
    if not harness.is_file():
        return PlanError(f"Code Mode harness is missing: {harness}")
    if kind == "bwrap":
        return build_bwrap_plan(runtime=runtime, harness=harness)
    return build_subprocess_plan(runtime=runtime, harness=harness)


def redact_text(text: str) -> str:
    """Redact credential-shaped ``KEY=value`` pairs from diagnostics."""
    return _SECRET_RE.sub(lambda match: f"{match.group(1)}=***", text)


def _safe_parse(line: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(line)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def _write(stream: Any, message: dict[str, Any]) -> bool:
    try:
        stream.write((_json_text(message) + "\n").encode("utf-8"))
        stream.flush()
    except (BrokenPipeError, OSError, ValueError):
        return False
    return True


def _reply(stream: Any, call_id: int, ok: bool, payload: Any) -> bool:
    if ok:
        try:
            text = _json_text({"value": payload})
        except (TypeError, ValueError) as exc:
            ok = False
            text = f"result is not JSON-serializable: {exc}"
    else:
        text = str(payload)
    return _write(stream, {"type": "reply", "id": call_id, "ok": ok, "json": text})


def _handle_call(
    message: dict[str, Any],
    handlers: Handlers | None,
    calls: int,
    max_calls: int,
) -> tuple[int, bool, Any]:
    call_id = message.get("id")
    if not isinstance(call_id, int) or call_id < 0:
        return -1, False, "invalid call id"
    calls += 1
    if calls > max_calls:
        return call_id, False, f"sandbox call limit reached ({max_calls})"
    method = message.get("method")
    if handlers is None or method not in handlers:
        return call_id, False, f"unknown sandbox method: {method}"
    target = message.get("target")
    if not isinstance(target, str):
        return call_id, False, "sandbox target must be a string"
    try:
        value = handlers[method](target, message.get("args"))
    except Exception as exc:
        return call_id, False, f"{type(exc).__name__}: {exc}"
    return call_id, True, value


def run_in_sandbox(
    request: SandboxRequest,
    handlers: Handlers | None = None,
    *,
    plan: SandboxPlan | PlanError | None = None,
    env: dict[str, str] | None = None,
) -> SandboxResult:
    """Run one code string in the boundary and return its normalized result."""
    started = time.monotonic()
    limits = request.limits

    def elapsed() -> int:
        return int((time.monotonic() - started) * 1000)

    if request.code is None or not isinstance(request.code, str):
        return SandboxResult(ok=False, message="code must be a string", duration_ms=elapsed())
    if len(request.code) > limits.max_code_chars:
        return SandboxResult(
            ok=False,
            message=f"code is {len(request.code)} characters; the limit is {limits.max_code_chars}",
            duration_ms=elapsed(),
        )
    if request.mode == "execute" and handlers is None:
        return SandboxResult(ok=False, message="execute mode requires handlers", duration_ms=elapsed())

    owned_plan = plan is None
    resolved = plan if plan is not None else default_plan(env)
    if isinstance(resolved, PlanError):
        return SandboxResult(ok=False, message=resolved.message, duration_ms=elapsed())

    stderr_file = tempfile.TemporaryFile()
    try:
        try:
            proc = subprocess.Popen(
                resolved.cmd,
                cwd=resolved.cwd,
                env=resolved.env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=stderr_file,
                bufsize=0,
            )
        except OSError as exc:
            return SandboxResult(
                ok=False,
                message=f"could not start the sandbox: {exc}",
                duration_ms=elapsed(),
            )

        job = {
            "type": "job",
            "mode": request.mode,
            "code": request.code,
            "catalog": _json_text(request.catalog) if request.mode == "search" and request.catalog else None,
            "namespaces": _json_text(request.namespaces) if request.mode == "execute" and request.namespaces else None,
            "maxCalls": limits.max_calls,
        }
        if proc.stdin is None or not _write(proc.stdin, job):
            _terminate(proc)
            return SandboxResult(ok=False, message="could not send the job to the sandbox", duration_ms=elapsed())

        done: dict[str, Any] | None = None
        failure: str | None = None
        timed_out = False
        calls = 0
        buffer = b""
        deadline = time.monotonic() + (limits.timeout_ms / 1000.0)
        selector = selectors.DefaultSelector()
        if proc.stdout is None:
            _terminate(proc)
            return SandboxResult(ok=False, message="sandbox stdout is unavailable", duration_ms=elapsed())
        selector.register(proc.stdout, selectors.EVENT_READ)
        try:
            while done is None and failure is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break
                if not selector.select(remaining):
                    timed_out = True
                    break
                chunk = os.read(proc.stdout.fileno(), 65536)
                if not chunk:
                    break
                buffer += chunk
                if len(buffer) > MAX_PROTOCOL_BYTES:
                    failure = f"sandbox protocol line exceeded {MAX_PROTOCOL_BYTES} bytes"
                    break
                while b"\n" in buffer:
                    raw, buffer = buffer.split(b"\n", 1)
                    message = _safe_parse(raw.decode("utf-8", errors="replace"))
                    if message is None:
                        continue
                    kind = message.get("type")
                    if kind == "call":
                        call_id, ok, payload = _handle_call(message, handlers, calls, limits.max_calls)
                        if call_id < 0:
                            continue
                        calls += 1
                        if not _reply(proc.stdin, call_id, ok, payload):
                            failure = "sandbox closed while a call was in flight"
                            break
                        continue
                    if kind == "done":
                        done = message
                        break
                    if kind == "error":
                        failure = str(message.get("message") or "sandbox error")
                        break
        finally:
            selector.close()

        _terminate(proc)
        exit_code = proc.returncode
        stderr_file.seek(0)
        stderr_raw = stderr_file.read().decode("utf-8", errors="replace")
        stderr = redact_text(stderr_raw[:STDERR_CAP])

        if owned_plan and resolved.cleanup_dir:
            shutil.rmtree(resolved.cleanup_dir, ignore_errors=True)

        if timed_out:
            return SandboxResult(
                ok=False,
                message=f"sandbox timed out after {limits.timeout_ms}ms",
                stderr=stderr,
                duration_ms=elapsed(),
            )
        if failure is not None:
            return SandboxResult(ok=False, message=failure, stderr=stderr, duration_ms=elapsed())
        if done is None:
            return SandboxResult(
                ok=False,
                message=f"sandbox exited {exit_code} without returning a result",
                stderr=stderr,
                duration_ms=elapsed(),
            )

        raw_json = done.get("json")
        if not isinstance(raw_json, str):
            return SandboxResult(
                ok=False, message="sandbox returned invalid JSON", stderr=stderr, duration_ms=elapsed()
            )
        try:
            value = json.loads(raw_json)
        except json.JSONDecodeError:
            return SandboxResult(
                ok=False, message="sandbox returned invalid JSON", stderr=stderr, duration_ms=elapsed()
            )

        truncated = False
        if len(raw_json) > limits.max_result_chars:
            value = {
                "truncated": True,
                "note": f"result was {len(raw_json)} characters; the limit is {limits.max_result_chars}",
            }
            truncated = True

        logs = done.get("logs")
        log_items = tuple(item for item in logs if isinstance(item, str)) if isinstance(logs, list) else ()
        reported_calls = done.get("calls")
        return SandboxResult(
            ok=True,
            value=value,
            calls=reported_calls if isinstance(reported_calls, int) else calls,
            logs=log_items,
            duration_ms=elapsed(),
            truncated=truncated,
        )
    finally:
        stderr_file.close()


def _terminate(proc: subprocess.Popen[bytes]) -> None:
    """Close stdin, then make sure the child is gone."""
    try:
        if proc.stdin is not None:
            proc.stdin.close()
    except OSError:
        pass
    if proc.poll() is None:
        try:
            proc.kill()
        except OSError:
            pass
    try:
        proc.wait(timeout=1)
    except subprocess.TimeoutExpired:
        pass
