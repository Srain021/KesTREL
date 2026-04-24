"""hashcat offline cracking wrapper."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

from ..config import Settings
from ..core.paths import PathTraversalError, safe_path
from ..domain import entities as ent
from ..domain.errors import DomainError
from ..executor import ToolNotFoundError, resolve_binary, run_command
from ..logging import audit_event
from ..security import ScopeGuard
from .base import ToolModule, ToolResult, ToolSpec

COMMON_HASHCAT_MODES = {
    1000: "NTLM",
    5600: "NetNTLMv2",
    13100: "Kerberos 5 TGS-REP etype 23",
    18200: "Kerberos 5 AS-REP etype 23",
    19700: "Kerberos 5 TGS-REP etype 18",
    19900: "Kerberos 5 Pre-Auth etype 18",
    3200: "bcrypt",
    0: "MD5",
}


class HashcatModule(ToolModule):
    id = "hashcat"

    def __init__(self, settings: Settings, scope_guard: ScopeGuard) -> None:
        super().__init__(settings, scope_guard)
        block = getattr(self.settings.tools, self.id, None)
        self._binary_hint = _block_get(block, "binary")
        self._wordlists_dir = str(_block_get(block, "wordlists_dir") or ".")
        self._hashes_dir = str(_block_get(block, "hashes_dir") or "~/.kestrel/runs/hashcat")

    def _binary(self) -> str:
        return resolve_binary(self._binary_hint, "hashcat")

    def specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="hashcat_crack",
                description="Run hashcat offline cracking and seal cracked plaintexts into CredentialService.",
                input_schema={
                    "type": "object",
                    "required": ["hash_mode", "attack_mode"],
                    "properties": {
                        "hash_mode": {"type": "integer"},
                        "attack_mode": {"type": "integer", "enum": [0, 3]},
                        "hashes": {"type": "array", "items": {"type": "string"}},
                        "hash_file": {"type": "string"},
                        "credential_refs": {"type": "array", "items": {"type": "string"}},
                        "wordlist": {"type": "string"},
                        "mask": {"type": "string"},
                        "username_in_hash": {"type": "boolean", "default": False},
                        "workload_profile": {"type": "integer", "minimum": 1, "maximum": 4, "default": 2},
                        "timeout_sec": {"type": "integer", "minimum": 30, "maximum": 86400, "default": 3600},
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_crack,
                dangerous=True,
                tags=["cracking", "credentials", "offline"],
                phase="post_exploit",
                complexity_tier=4,
                preferred_model_tier="strong",
                output_trust="sensitive",
                when_to_use=["Captured hashes need offline password recovery."],
                when_not_to_use=["No written authorization for password cracking."],
                prerequisites=["hashcat binary installed.", "Wordlist/hash files stay under configured safe directories."],
                follow_ups=["Use created credential references with NetExec or Impacket."],
                pitfalls=[
                    "This tool returns detailed cracked values in structured output; treat the response as sensitive.",
                    "Do not run against hashes outside the written engagement authorization.",
                ],
            ),
            ToolSpec(
                name="hashcat_modes",
                description="Return common hashcat mode IDs useful for red-team workflows.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_modes,
                tags=["meta", "free"],
            ),
            ToolSpec(
                name="hashcat_version",
                description="Return the installed hashcat version.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_version,
                tags=["meta", "free"],
            ),
        ]

    async def _handle_crack(self, arguments: dict[str, Any]) -> ToolResult:
        try:
            binary = self._binary()
            hash_path, hash_count = await self._hash_input(arguments)
            candidate = self._candidate_input(arguments)
        except (ToolNotFoundError, PathTraversalError, DomainError, ValueError) as exc:
            return ToolResult.error(str(exc))

        run_id = uuid.uuid4().hex
        out_dir = _expanded_dir(self._hashes_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        outfile = out_dir / f"hashcat_{run_id}.out"
        potfile = out_dir / f"hashcat_{run_id}.pot"
        argv = [
            binary,
            "-m",
            str(int(arguments["hash_mode"])),
            "-a",
            str(int(arguments["attack_mode"])),
            str(hash_path),
            str(candidate),
            "--outfile",
            str(outfile),
            "--potfile-path",
            str(potfile),
            "--outfile-format",
            "3",
            "-w",
            str(int(arguments.get("workload_profile") or 2)),
        ]
        if bool(arguments.get("username_in_hash", False)):
            argv.append("--username")

        if self.settings.security.dry_run:
            return ToolResult(
                text=f"[dry-run] would run hashcat against {hash_count} hash(es).",
                structured={"dry_run": True, "argv": argv, "hash_count": hash_count},
            )

        result = await run_command(
            argv,
            timeout_sec=int(arguments.get("timeout_sec") or 3600),
            max_output_bytes=self.settings.execution.max_output_bytes,
        )
        cracked = _parse_hashcat_outfile(outfile.read_text(encoding="utf-8", errors="replace") if outfile.exists() else "")
        credential_ids = await self._seal_cracked(cracked, int(arguments["hash_mode"]))
        cracked_details = [
            {
                "hash": item["hash"],
                "plaintext": item["plaintext"],
                "credential_id": credential_ids[idx] if idx < len(credential_ids) else None,
            }
            for idx, item in enumerate(cracked)
        ]
        audit_event(
            self.log,
            "hashcat.crack",
            hash_mode=int(arguments["hash_mode"]),
            hash_count=hash_count,
            cracked=len(cracked),
            exit_code=result.exit_code,
        )
        return ToolResult(
            text=f"hashcat processed {hash_count} hash(es); cracked {len(cracked)} secret(s).",
            structured={
                "hash_mode": int(arguments["hash_mode"]),
                "mode_name": COMMON_HASHCAT_MODES.get(int(arguments["hash_mode"])),
                "hash_count": hash_count,
                "cracked_count": len(cracked),
                "cracked": cracked_details,
                "credentials_created": credential_ids,
                "outfile": str(outfile),
                "potfile": str(potfile),
                "exit_code": result.exit_code,
                "stdout_tail": result.stdout[-4000:],
                "stderr_tail": result.stderr[-2000:],
                "truncated": result.truncated,
            },
            is_error=not result.ok and len(cracked) == 0,
        )

    async def _handle_modes(self, _arguments: dict[str, Any]) -> ToolResult:
        modes = [{"mode": mode, "name": name} for mode, name in sorted(COMMON_HASHCAT_MODES.items())]
        return ToolResult(text=f"{len(modes)} common hashcat modes available.", structured={"modes": modes})

    async def _handle_version(self, _arguments: dict[str, Any]) -> ToolResult:
        try:
            binary = self._binary()
        except ToolNotFoundError as exc:
            return ToolResult.error(str(exc))
        result = await run_command([binary, "--version"], timeout_sec=30, max_output_bytes=64 * 1024)
        raw = (result.stdout or result.stderr).strip()
        return ToolResult(text=raw, structured={"raw": raw, "exit_code": result.exit_code}, is_error=not result.ok)

    async def _hash_input(self, arguments: dict[str, Any]) -> tuple[Path, int]:
        sources = [
            bool(arguments.get("hashes")),
            bool(arguments.get("hash_file")),
            bool(arguments.get("credential_refs")),
        ]
        if sum(1 for present in sources if present) != 1:
            raise ValueError("Provide exactly one of hashes, hash_file, or credential_refs.")

        base = _expanded_dir(self._hashes_dir)
        base.mkdir(parents=True, exist_ok=True)
        if arguments.get("hash_file"):
            path = safe_path(base, str(arguments["hash_file"]))
            text = path.read_text(encoding="utf-8", errors="replace")
            return path, len([line for line in text.splitlines() if line.strip()])

        if arguments.get("credential_refs"):
            hashes = await self._unseal_refs([str(r) for r in arguments["credential_refs"]])
        else:
            hashes = [str(h).strip() for h in arguments.get("hashes", []) if str(h).strip()]
        if not hashes:
            raise ValueError("No hashes supplied.")
        path = base / f"hashcat_input_{uuid.uuid4().hex}.txt"
        path.write_text("\n".join(hashes) + "\n", encoding="utf-8")
        return path, len(hashes)

    def _candidate_input(self, arguments: dict[str, Any]) -> Path | str:
        attack_mode = int(arguments["attack_mode"])
        if attack_mode == 0:
            wordlist = str(arguments.get("wordlist") or "").strip()
            if not wordlist:
                raise ValueError("attack_mode=0 requires wordlist.")
            base = _expanded_dir(self._wordlists_dir)
            return safe_path(base, wordlist)
        mask = str(arguments.get("mask") or "").strip()
        if not mask:
            raise ValueError("attack_mode=3 requires mask.")
        return mask

    async def _unseal_refs(self, refs: list[str]) -> list[str]:
        from ..core.context import current_context_or_none

        ctx = current_context_or_none()
        if ctx is None or not ctx.has_engagement():
            raise DomainError("credential_refs require an active engagement context.")
        return [await ctx.credential.unseal(ref) for ref in refs]

    async def _seal_cracked(self, cracked: list[dict[str, str]], hash_mode: int) -> list[str]:
        ids: list[str] = []
        if not cracked:
            return ids
        try:
            from ..core.context import current_context_or_none

            ctx = current_context_or_none()
            if ctx is None or not ctx.has_engagement():
                return ids
            engagement_id = ctx.require_engagement()
            for item in cracked:
                cred = await ctx.credential.seal(
                    engagement_id=engagement_id,
                    kind=ent.CredentialKind.PASSWORD_PLAINTEXT,
                    identity=item["hash"][:64],
                    plaintext=item["plaintext"],
                    obtained_from_tool="hashcat_crack",
                    secret_metadata={"hash_mode": str(hash_mode), "hash_prefix": item["hash"][:16]},
                    tags=["cracked", "hashcat"],
                )
                ids.append(str(cred.id))
        except Exception as exc:  # noqa: BLE001
            self.log.warning("hashcat.credential_persist_failed", error=str(exc))
        return ids


def _parse_hashcat_outfile(text: str) -> list[dict[str, str]]:
    cracked: list[dict[str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        hash_part, plaintext = line.rsplit(":", 1)
        if hash_part and plaintext:
            cracked.append({"hash": hash_part, "plaintext": plaintext})
    return cracked


def _expanded_dir(raw: str) -> Path:
    path = Path(os.path.expandvars(os.path.expanduser(raw)))
    return path if path.is_absolute() else Path.cwd() / path


def _block_get(block: Any, key: str) -> Any:
    if isinstance(block, dict):
        return block.get(key)
    return getattr(block, key, None)
