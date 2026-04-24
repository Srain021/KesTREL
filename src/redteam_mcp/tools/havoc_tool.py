"""Havoc Framework tools.

Havoc's teamserver (``havoc server``) takes a profile YAML file and
exposes a websocket+REST API for operators. The GUI client is a Qt
application that's impractical to drive from an LLM.

Instead, for LLM automation we target the CLI/API surface:

Tools:
    * ``havoc_build_teamserver``   go-compile the teamserver from sources
    * ``havoc_start_teamserver``   spawn the teamserver in the background
    * ``havoc_stop_teamserver``    stop the teamserver
    * ``havoc_teamserver_status``  PID file status
    * ``havoc_lint_profile``       syntactically validate a profile YAML
    * ``havoc_generate_agent_note`` produce a command-line cheat for the
      operator (no execution; purely a helper).

Note: generating Demon payloads is GUI-driven in upstream Havoc. For now
we expose the management surface only; payload generation belongs to the
next release once the REST client is stable.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from ..config import Settings
from ..executor import resolve_binary, run_command
from ..logging import audit_event
from ..security import ScopeGuard
from .base import ToolModule, ToolResult, ToolSpec


_PID_FILE_NAME = "havoc-teamserver.pid"


class HavocModule(ToolModule):
    id = "havoc"

    def __init__(self, settings: Settings, scope_guard: ScopeGuard) -> None:
        super().__init__(settings, scope_guard)
        block = self.settings.tools.havoc
        self._binary_hint: str | None = getattr(block, "binary", None)
        self._source_dir: str | None = getattr(block, "source_dir", None)
        self._default_profile: str | None = getattr(block, "profile", None)
        runs_dir = settings.expanded_path(settings.execution.working_dir)
        runs_dir.mkdir(parents=True, exist_ok=True)
        self._pid_file = runs_dir / _PID_FILE_NAME

    def _binary(self) -> str:
        return resolve_binary(self._binary_hint, "havoc")

    def specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="havoc_build_teamserver",
                description=(
                    "Compile the Havoc teamserver binary from source using ``go build``. "
                    "Requires Go >= 1.20 on PATH. Outputs a single havoc.exe/havoc binary."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "source_dir": {
                            "type": "string",
                            "description": "Root of a Havoc git checkout. Uses configured default otherwise.",
                        },
                        "output": {
                            "type": "string",
                            "description": "Output path for the compiled binary.",
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_build,
                tags=["c2", "build"],
            ),
            ToolSpec(
                name="havoc_start_teamserver",
                description="Start the Havoc teamserver in the background using a profile YAML.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "profile": {"type": "string"},
                        "verbose": {"type": "boolean", "default": True},
                        "debug": {"type": "boolean", "default": False},
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_start,
                dangerous=True,
                tags=["c2"],
            ),
            ToolSpec(
                name="havoc_stop_teamserver",
                description="Stop the Havoc teamserver process started by this MCP.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_stop,
                tags=["c2"],
            ),
            ToolSpec(
                name="havoc_teamserver_status",
                description="Return whether the Havoc teamserver is running.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_status,
                tags=["c2", "meta"],
            ),
            ToolSpec(
                name="havoc_lint_profile",
                description=(
                    "Validate a Havoc teamserver profile YAML: required sections, valid "
                    "listener types, non-empty operator passwords. Does NOT start the "
                    "server."
                ),
                input_schema={
                    "type": "object",
                    "required": ["profile"],
                    "properties": {
                        "profile": {"type": "string", "description": "Path to the profile YAML."},
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_lint,
                tags=["c2", "lint"],
            ),
            ToolSpec(
                name="havoc_generate_demon_hint",
                description=(
                    "Emit a structured reminder of how to generate a Demon payload in the "
                    "Havoc client GUI for the specified listener + OS. Informational only."
                ),
                input_schema={
                    "type": "object",
                    "required": ["listener_name"],
                    "properties": {
                        "listener_name": {"type": "string"},
                        "os": {"type": "string", "enum": ["windows"], "default": "windows"},
                        "arch": {"type": "string", "enum": ["x64", "x86"], "default": "x64"},
                        "sleep_obf": {
                            "type": "string",
                            "enum": ["none", "ekko", "foliage", "zilean"],
                            "default": "foliage",
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_demon_hint,
                tags=["c2", "helper"],
            ),
        ]

    # -----------------------------------------------------------------------

    async def _handle_build(self, arguments: dict[str, Any]) -> ToolResult:
        src = arguments.get("source_dir") or self._source_dir
        if not src:
            return ToolResult.error(
                "No source_dir given and config.tools.havoc.source_dir is unset."
            )
        src_path = self.settings.expanded_path(src)
        if not src_path.is_dir():
            return ToolResult.error(f"source_dir {src_path} does not exist.")
        output = arguments.get("output") or str(
            src_path / ("havoc.exe" if sys.platform == "win32" else "havoc")
        )

        try:
            go_bin = resolve_binary(None, "go")
        except Exception as exc:  # noqa: BLE001
            return ToolResult.error(f"Go compiler not found: {exc}")

        argv = [go_bin, "build", "-o", output, "-ldflags", "-s -w", "./teamserver"]
        if self.settings.security.dry_run:
            return ToolResult(
                text=f"[dry-run] would compile havoc teamserver in {src_path}",
                structured={"dry_run": True, "argv": argv, "cwd": str(src_path)},
            )

        result = await run_command(
            argv,
            cwd=str(src_path),
            timeout_sec=1800,
            max_output_bytes=self.settings.execution.max_output_bytes,
        )
        audit_event(
            self.log,
            "havoc.build",
            output=output,
            exit_code=result.exit_code,
            duration_sec=result.duration_sec,
        )
        return ToolResult(
            text=(
                f"Havoc build {'succeeded' if result.ok else 'FAILED'} "
                f"in {result.duration_sec:.1f}s. Binary: {output}"
            ),
            structured={
                "exit_code": result.exit_code,
                "output": output,
                "duration_sec": result.duration_sec,
                "stdout_tail": result.stdout[-4000:],
                "stderr_tail": result.stderr[-4000:],
            },
            is_error=not result.ok,
        )

    async def _handle_start(self, arguments: dict[str, Any]) -> ToolResult:
        if self._pid_file.exists():
            try:
                pid = int(self._pid_file.read_text("utf-8").strip())
                if _alive(pid):
                    return ToolResult.error(f"Havoc teamserver already running PID {pid}.")
            except (ValueError, OSError):
                pass

        profile = arguments.get("profile") or self._default_profile
        if not profile:
            return ToolResult.error(
                "No profile specified and config.tools.havoc.profile is unset."
            )

        profile_path = self.settings.expanded_path(profile)
        if not profile_path.is_file():
            return ToolResult.error(f"Profile {profile_path} not found.")

        binary = self._binary()
        argv: list[str] = [binary, "server", "--profile", str(profile_path)]
        if arguments.get("verbose", True):
            argv.append("-v")
        if arguments.get("debug", False):
            argv.append("--debug")

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
            return ToolResult.error(f"Failed to spawn havoc teamserver: {exc}")

        self._pid_file.write_text(str(proc.pid), encoding="utf-8")
        audit_event(self.log, "havoc.start", pid=proc.pid, profile=str(profile_path))
        return ToolResult(
            text=f"Havoc teamserver started, PID {proc.pid}. Logs: {log_path}",
            structured={"pid": proc.pid, "profile": str(profile_path), "log_path": str(log_path)},
        )

    async def _handle_stop(self, _arguments: dict[str, Any]) -> ToolResult:
        if not self._pid_file.exists():
            return ToolResult(text="Havoc teamserver is not running.", structured={"running": False})
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
        audit_event(self.log, "havoc.stop", pid=pid)
        return ToolResult(text=f"Stopped havoc teamserver PID {pid}.", structured={"stopped_pid": pid})

    async def _handle_status(self, _arguments: dict[str, Any]) -> ToolResult:
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

    async def _handle_lint(self, arguments: dict[str, Any]) -> ToolResult:
        path = self.settings.expanded_path(arguments["profile"])
        if not path.is_file():
            return ToolResult.error(f"Profile {path} not found.")
        try:
            raw = yaml.safe_load(path.read_text("utf-8"))
        except yaml.YAMLError as exc:
            return ToolResult.error(f"Profile is not valid YAML: {exc}")
        if not isinstance(raw, dict):
            return ToolResult.error("Profile root must be a mapping.")

        problems: list[str] = []
        teamserver = raw.get("Teamserver") or raw.get("teamserver")
        if not teamserver:
            problems.append("Missing 'Teamserver' section.")
        operators = raw.get("Operators") or raw.get("operators")
        if not operators:
            problems.append("Missing 'Operators' section — no one can log in.")
        else:
            user_map = operators.get("user") if isinstance(operators, dict) else None
            if isinstance(user_map, dict):
                for name, block in user_map.items():
                    pwd = (block or {}).get("Password") or (block or {}).get("password")
                    if not pwd or len(str(pwd)) < 8:
                        problems.append(f"Operator '{name}' has weak or missing password (<8 chars).")

        listeners = raw.get("Listeners") or raw.get("listeners")
        if not listeners:
            problems.append("No Listeners defined (Demon agents will have nowhere to call home).")

        ok = not problems
        audit_event(self.log, "havoc.lint", path=str(path), ok=ok, problems=problems)
        return ToolResult(
            text=("Profile is valid." if ok else f"{len(problems)} issue(s) found."),
            structured={"path": str(path), "ok": ok, "problems": problems},
            is_error=not ok,
        )

    async def _handle_demon_hint(self, arguments: dict[str, Any]) -> ToolResult:
        listener = arguments["listener_name"]
        os_name = arguments.get("os", "windows")
        arch = arguments.get("arch", "x64")
        sleep_obf = arguments.get("sleep_obf", "foliage")
        hint = {
            "client_steps": [
                "Open Havoc client GUI",
                "Menu: Attack -> Payload -> Demon",
                f"Listener: {listener}",
                f"Arch: {arch}",
                f"Format: Windows Exe (or Shellcode/DLL)",
                f"Sleep Obfuscation: {sleep_obf.upper()}",
                "Indirect Syscall: enabled (for EDR evasion)",
                "AMSI Patch: enabled",
                "Stack Spoof: enabled",
                "Click Generate and save the binary.",
            ],
            "notes": (
                "Havoc does not currently expose payload generation via a stable REST API, "
                "so the operator must drive the GUI. These steps mirror recommended "
                "production hardening defaults."
            ),
            "os": os_name,
        }
        return ToolResult(
            text=f"Demon payload generation hint for listener '{listener}'.",
            structured=hint,
        )


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
