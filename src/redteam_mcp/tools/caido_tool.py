"""Caido tools.

Caido is primarily a desktop/GUI application. Its CLI build
(``caido-cli``) exposes a headless proxy for scripted engagements — that's
the surface we drive here.

Tools:
    * ``caido_start``              — spawn caido-cli in the background
    * ``caido_stop``               — stop it
    * ``caido_status``             — check run state
    * ``caido_replay_request``     — send one HTTP request through a given
      proxy and return the response (works with ANY proxy, not just Caido)
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx

from ..config import Settings
from ..executor import resolve_binary
from ..logging import audit_event
from ..security import ScopeGuard
from .base import ToolModule, ToolResult, ToolSpec

_PID_FILE_NAME = "caido-cli.pid"


class CaidoModule(ToolModule):
    id = "caido"

    def __init__(self, settings: Settings, scope_guard: ScopeGuard) -> None:
        super().__init__(settings, scope_guard)
        block = self.settings.tools.caido
        self._binary_hint: str | None = getattr(block, "binary", None) or getattr(
            block, "cli_binary", None
        )
        runs_dir = settings.expanded_path(settings.execution.working_dir)
        runs_dir.mkdir(parents=True, exist_ok=True)
        self._pid_file = runs_dir / _PID_FILE_NAME

    def _binary(self) -> str:
        return resolve_binary(self._binary_hint, "caido-cli")

    def specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="caido_start",
                description=(
                    "Start the headless Caido proxy (caido-cli) in the background so "
                    "traffic can be logged and replayed. Default listen is 127.0.0.1:8080."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "listen_addr": {
                            "type": "string",
                            "default": "127.0.0.1:8080",
                        },
                        "project": {
                            "type": "string",
                            "description": "Path to an existing .caido project file.",
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_start,
                tags=["proxy", "web"],
            ),
            ToolSpec(
                name="caido_stop",
                description="Stop the Caido CLI proxy launched by caido_start.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_stop,
                tags=["proxy"],
            ),
            ToolSpec(
                name="caido_status",
                description="Return whether the Caido CLI proxy is currently running.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_status,
                tags=["proxy", "meta"],
            ),
            ToolSpec(
                name="caido_replay_request",
                description=(
                    "Send one HTTP request through a proxy (default 127.0.0.1:8080) and "
                    "return the raw response. Useful for manually re-testing a request "
                    "captured during a Caido session. Target URL MUST be in scope."
                ),
                input_schema={
                    "type": "object",
                    "required": ["url"],
                    "properties": {
                        "url": {"type": "string", "format": "uri"},
                        "method": {
                            "type": "string",
                            "default": "GET",
                            "enum": ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
                        },
                        "headers": {
                            "type": "object",
                            "additionalProperties": {"type": "string"},
                        },
                        "body": {"type": "string"},
                        "proxy": {
                            "type": "string",
                            "default": "http://127.0.0.1:8080",
                            "description": "Proxy URL; set to empty string to go direct.",
                        },
                        "verify_tls": {"type": "boolean", "default": False},
                        "timeout_sec": {
                            "type": "number",
                            "minimum": 1,
                            "maximum": 120,
                            "default": 30,
                        },
                        "follow_redirects": {"type": "boolean", "default": False},
                        "max_body_bytes": {
                            "type": "integer",
                            "minimum": 1024,
                            "maximum": 2_000_000,
                            "default": 200_000,
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_replay,
                dangerous=True,
                requires_scope_field="url",
                tags=["web", "active"],
            ),
        ]

    async def _handle_start(self, arguments: dict[str, Any]) -> ToolResult:
        if self._pid_file.exists():
            try:
                pid = int(self._pid_file.read_text("utf-8").strip())
                if _pid_alive(pid):
                    return ToolResult.error(
                        f"Caido CLI already running with PID {pid}. Call caido_stop first."
                    )
            except (ValueError, OSError):
                pass

        binary = self._binary()
        argv: list[str] = [binary, "--listen", arguments.get("listen_addr", "127.0.0.1:8080")]
        if project := arguments.get("project"):
            argv += ["--project", project]

        if self.settings.security.dry_run:
            return ToolResult(
                text=f"[dry-run] would start: {' '.join(argv)}",
                structured={"dry_run": True, "argv": argv},
            )

        log_path = self._pid_file.with_suffix(".log")
        try:
            log_fh = log_path.open("ab")
            proc = subprocess.Popen(  # noqa: S603
                argv,
                stdout=log_fh,
                stderr=log_fh,
                stdin=subprocess.DEVNULL,
                cwd=str(Path(binary).parent),
                creationflags=(
                    subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
                ),
            )
        except OSError as exc:
            return ToolResult.error(f"Failed to spawn caido-cli: {exc}")

        self._pid_file.write_text(str(proc.pid), encoding="utf-8")
        audit_event(self.log, "caido.start", pid=proc.pid, listen=arguments.get("listen_addr"))
        return ToolResult(
            text=f"Caido CLI started: PID {proc.pid} on {arguments.get('listen_addr', '127.0.0.1:8080')}.",
            structured={
                "pid": proc.pid,
                "listen_addr": arguments.get("listen_addr", "127.0.0.1:8080"),
                "log_path": str(log_path),
            },
        )

    async def _handle_stop(self, _arguments: dict[str, Any]) -> ToolResult:
        if not self._pid_file.exists():
            return ToolResult(text="Caido CLI is not running.", structured={"running": False})
        try:
            pid = int(self._pid_file.read_text("utf-8").strip())
        except ValueError:
            self._pid_file.unlink(missing_ok=True)
            return ToolResult.error("PID file malformed; cleaned up.")

        if not _pid_alive(pid):
            self._pid_file.unlink(missing_ok=True)
            return ToolResult(text=f"PID {pid} already exited.", structured={"running": False})

        try:
            if sys.platform == "win32":
                os.kill(pid, signal.CTRL_BREAK_EVENT)
            else:
                os.kill(pid, signal.SIGTERM)
        except OSError as exc:
            return ToolResult.error(f"Failed to kill PID {pid}: {exc}")

        self._pid_file.unlink(missing_ok=True)
        audit_event(self.log, "caido.stop", pid=pid)
        return ToolResult(text=f"Stopped caido-cli PID {pid}.", structured={"stopped_pid": pid})

    async def _handle_status(self, _arguments: dict[str, Any]) -> ToolResult:
        if not self._pid_file.exists():
            return ToolResult(text="not running", structured={"running": False})
        try:
            pid = int(self._pid_file.read_text("utf-8").strip())
        except ValueError:
            return ToolResult.error("PID file corrupt")
        alive = _pid_alive(pid)
        if not alive:
            self._pid_file.unlink(missing_ok=True)
        return ToolResult(
            text=f"pid={pid} running={alive}", structured={"pid": pid, "running": alive}
        )

    async def _handle_replay(self, arguments: dict[str, Any]) -> ToolResult:
        url = arguments["url"]
        method = arguments.get("method", "GET").upper()
        headers = arguments.get("headers") or {}
        body = arguments.get("body")
        proxy = arguments.get("proxy") or "http://127.0.0.1:8080"
        verify = bool(arguments.get("verify_tls", False))
        timeout = float(arguments.get("timeout_sec", 30))
        follow = bool(arguments.get("follow_redirects", False))
        max_body = int(arguments.get("max_body_bytes", 200_000))

        self.scope_guard.ensure(url, tool_name="caido_replay_request")

        if self.settings.security.dry_run:
            return ToolResult(
                text=f"[dry-run] would {method} {url} via proxy={proxy}",
                structured={"dry_run": True, "url": url, "method": method, "proxy": proxy},
            )

        proxies = {"all://": proxy} if proxy else None
        try:
            async with httpx.AsyncClient(
                proxies=proxies,
                verify=verify,
                timeout=timeout,
                follow_redirects=follow,
            ) as client:
                resp = await client.request(method, url, headers=headers, content=body)
        except httpx.HTTPError as exc:
            return ToolResult.error(f"Replay failed: {exc}")

        body_preview = resp.text[:max_body]
        truncated = len(resp.text) > max_body
        audit_event(
            self.log,
            "caido.replay",
            url=url,
            method=method,
            status=resp.status_code,
            via_proxy=bool(proxy),
        )
        return ToolResult(
            text=f"{method} {url} -> HTTP {resp.status_code} ({len(resp.text)} bytes)",
            structured={
                "request": {
                    "url": url,
                    "method": method,
                    "headers": headers,
                    "via_proxy": proxy or None,
                },
                "response": {
                    "status_code": resp.status_code,
                    "headers": dict(resp.headers),
                    "body_preview": body_preview,
                    "body_truncated": truncated,
                    "content_length": len(resp.text),
                    "elapsed_sec": resp.elapsed.total_seconds(),
                },
            },
        )


def _pid_alive(pid: int) -> bool:
    if sys.platform == "win32":
        try:
            output = subprocess.check_output(  # noqa: S603,S607
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            return str(pid) in output
        except (OSError, subprocess.SubprocessError):
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False
