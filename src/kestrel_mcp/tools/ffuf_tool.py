"""ffuf web fuzzing wrapper."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config import Settings
from ..core.paths import PathTraversalError, safe_path
from ..domain import entities as ent
from ..executor import ToolNotFoundError, resolve_binary, run_command
from ..logging import audit_event
from ..security import ScopeGuard
from .base import ToolModule, ToolResult, ToolSpec


class FfufModule(ToolModule):
    id = "ffuf"

    def __init__(self, settings: Settings, scope_guard: ScopeGuard) -> None:
        super().__init__(settings, scope_guard)
        block = getattr(self.settings.tools, self.id, None)
        self._binary_hint = _block_get(block, "binary")
        self._wordlists_dir = str(_block_get(block, "wordlists_dir") or ".")

    def _binary(self) -> str:
        return resolve_binary(self._binary_hint, "ffuf")

    def enabled(self) -> bool:
        block = getattr(self.settings.tools, self.id, None)
        return bool(_block_get(block, "enabled"))

    def specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="ffuf_dir_bruteforce",
                description="Run ffuf directory fuzzing against an in-scope URL.",
                input_schema={
                    "type": "object",
                    "required": ["url", "wordlist"],
                    "properties": {
                        "url": {"type": "string"},
                        "wordlist": {"type": "string"},
                        "extensions": {"type": "string", "default": ""},
                        "threads": {"type": "integer", "minimum": 1, "maximum": 200, "default": 40},
                        "timeout_sec": {"type": "integer", "minimum": 10, "maximum": 3600},
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_dir,
                dangerous=True,
                requires_scope_field="url",
                tags=["web", "fuzzing", "active"],
                when_to_use=["User asks for directory/content discovery on a live web target."],
                when_not_to_use=["Target has not been confirmed live; run httpx_probe first."],
                prerequisites=["ffuf binary installed.", "Wordlist is under tools.ffuf.wordlists_dir."],
                pitfalls=["Never pass absolute wordlist paths; safe_path rejects them."],
            ),
            ToolSpec(
                name="ffuf_param_fuzz",
                description="Run ffuf parameter-name fuzzing against an in-scope URL.",
                input_schema={
                    "type": "object",
                    "required": ["url", "wordlist"],
                    "properties": {
                        "url": {"type": "string"},
                        "wordlist": {"type": "string"},
                        "timeout_sec": {"type": "integer", "minimum": 10, "maximum": 3600},
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_param,
                dangerous=True,
                requires_scope_field="url",
                tags=["web", "fuzzing", "active"],
                prerequisites=["ffuf binary installed.", "URL is inside authorized_scope."],
            ),
            ToolSpec(
                name="ffuf_version",
                description="Return the installed ffuf version.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_version,
                tags=["meta", "free"],
            ),
        ]

    async def _handle_dir(self, arguments: dict[str, Any]) -> ToolResult:
        url = str(arguments["url"]).strip()
        await self.ensure_scope(url, tool_name="ffuf_dir_bruteforce")
        fuzz_url = url.rstrip("/") + "/FUZZ"
        argv_or_error = self._base_argv(fuzz_url, str(arguments["wordlist"]))
        if isinstance(argv_or_error, ToolResult):
            return argv_or_error
        argv = argv_or_error
        if extensions := str(arguments.get("extensions") or "").strip():
            argv += ["-e", extensions]
        argv += ["-t", str(int(arguments.get("threads") or 40))]
        return await self._run_ffuf(argv, int(arguments.get("timeout_sec") or 300), "ffuf.dir")

    async def _handle_param(self, arguments: dict[str, Any]) -> ToolResult:
        url = str(arguments["url"]).strip()
        await self.ensure_scope(url, tool_name="ffuf_param_fuzz")
        fuzz_url = url if "FUZZ" in url else url + ("&FUZZ=1" if "?" in url else "?FUZZ=1")
        argv_or_error = self._base_argv(fuzz_url, str(arguments["wordlist"]))
        if isinstance(argv_or_error, ToolResult):
            return argv_or_error
        return await self._run_ffuf(
            argv_or_error,
            int(arguments.get("timeout_sec") or 300),
            "ffuf.param",
        )

    async def _handle_version(self, _arguments: dict[str, Any]) -> ToolResult:
        try:
            binary = self._binary()
        except ToolNotFoundError as exc:
            return ToolResult.error(str(exc))
        result = await run_command([binary, "-V"], timeout_sec=30, max_output_bytes=64 * 1024)
        raw = (result.stdout or result.stderr).strip()
        return ToolResult(
            text=raw.splitlines()[0] if raw else "",
            structured={"raw": raw, "exit_code": result.exit_code},
            is_error=not result.ok,
        )

    def _base_argv(self, fuzz_url: str, wordlist: str) -> list[str] | ToolResult:
        try:
            binary = self._binary()
            wordlist_path = self._wordlist_path(wordlist)
        except (ToolNotFoundError, PathTraversalError) as exc:
            return ToolResult.error(str(exc))
        return [binary, "-u", fuzz_url, "-w", str(wordlist_path), "-of", "json", "-s"]

    def _wordlist_path(self, wordlist: str) -> Path:
        base = Path(self._wordlists_dir).expanduser()
        if not base.is_absolute():
            base = Path.cwd() / base
        return safe_path(base, wordlist)

    async def _run_ffuf(self, argv: list[str], timeout_sec: int, event: str) -> ToolResult:
        if self.settings.security.dry_run:
            return ToolResult(text=f"[dry-run] would run: {' '.join(argv)}", structured={"argv": argv})
        result = await run_command(
            argv,
            timeout_sec=timeout_sec,
            max_output_bytes=self.settings.execution.max_output_bytes,
        )
        parsed = _parse_ffuf_json(result.stdout)

        target_ids: list[str] = []
        finding_ids: list[str] = []
        try:
            from ..core.context import current_context_or_none

            ctx = current_context_or_none()
            if ctx is not None and ctx.has_engagement():
                engagement_id = ctx.require_engagement()
                # Base URL is the first -u argument value
                base_url = argv[argv.index("-u") + 1] if "-u" in argv else ""
                # Remove FUZZ marker for base target
                clean_url = base_url.replace("FUZZ", "").rstrip("/&?")
                if clean_url:
                    base_t = await ctx.target.add(
                        engagement_id=engagement_id,
                        kind=ent.TargetKind.URL,
                        value=clean_url,
                        discovered_by_tool=event.replace(".", "_"),
                    )
                    target_ids.append(str(base_t.id))
                else:
                    base_t = None

                for r in parsed:
                    url = r.get("url")
                    if url and base_t is not None:
                        f = await ctx.finding.create(
                            engagement_id=engagement_id,
                            target_id=base_t.id,
                            title=f"Discovered path: {url}",
                            severity=ent.FindingSeverity.INFO,
                            discovered_by_tool=event.replace(".", "_"),
                            category=ent.FindingCategory.INFORMATION_DISCLOSURE,
                            description=f"ffuf discovered a reachable path. Status {r.get('status')}, length {r.get('length')}, words {r.get('words')}, lines {r.get('lines')}",
                        )
                        finding_ids.append(str(f.id))
        except Exception as persist_exc:  # noqa: BLE001
            self.log.warning("ffuf.persist_failed", error=str(persist_exc))

        audit_event(self.log, event, results=len(parsed), exit_code=result.exit_code)
        return ToolResult(
            text=f"ffuf returned {len(parsed)} result(s).",
            structured={
                "results": parsed,
                "count": len(parsed),
                "exit_code": result.exit_code,
                "stderr_tail": result.stderr[-2000:],
                "truncated": result.truncated,
                "targets_created": target_ids,
                "findings_created": finding_ids,
            },
            is_error=not result.ok,
        )


def _parse_ffuf_json(text: str) -> list[dict[str, Any]]:
    if not text.strip():
        return []
    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        return []
    results = raw.get("results") if isinstance(raw, dict) else None
    if not isinstance(results, list):
        return []
    return [
        {
            "url": item.get("url"),
            "status": item.get("status"),
            "length": item.get("length"),
            "words": item.get("words"),
            "lines": item.get("lines"),
            "input": item.get("input"),
        }
        for item in results
        if isinstance(item, dict)
    ]


def _block_get(block: Any, key: str) -> Any:
    if isinstance(block, dict):
        return block.get(key)
    return getattr(block, key, None)
