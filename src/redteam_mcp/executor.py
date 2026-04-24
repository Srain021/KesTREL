"""Async subprocess executor shared by every command-line tool wrapper.

Features:
    * Timeout enforcement via :func:`anyio.fail_after`.
    * Output capping so a misbehaving scan can't exhaust memory.
    * Streaming-safe byte handling (no partial multi-byte decode panics).
    * Audit-ready :class:`ExecutionResult` dataclass.
"""

from __future__ import annotations

import asyncio
import os
import shlex
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

import anyio

from .logging import get_logger

_log = get_logger(__name__)


class ExecutorError(Exception):
    """Base class for executor failures."""


class ToolNotFoundError(ExecutorError):
    """The requested binary is not installed / not on PATH / wrong path in config."""


class ExecutionTimeout(ExecutorError):
    """The command ran longer than the configured budget."""


@dataclass
class ExecutionResult:
    """Result of a single subprocess invocation."""

    argv: list[str]
    exit_code: int
    stdout: str
    stderr: str
    duration_sec: float
    truncated: bool = False
    timed_out: bool = False
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    def summary(self) -> str:
        head = shlex.join(self.argv[:1])
        return (
            f"{head} -> exit={self.exit_code} "
            f"dur={self.duration_sec:.2f}s "
            f"out={len(self.stdout)}B err={len(self.stderr)}B"
            f"{' TRUNCATED' if self.truncated else ''}"
            f"{' TIMEOUT' if self.timed_out else ''}"
        )


def resolve_binary(hint: str | None, default_name: str) -> str:
    """Resolve a binary path from an explicit config hint OR ``$PATH`` lookup.

    Raises :class:`ToolNotFoundError` if nothing is found.
    """

    if hint:
        p = Path(os.path.expanduser(hint))
        if p.is_file():
            return str(p)
        if shutil.which(hint):
            return shutil.which(hint)  # type: ignore[return-value]
        raise ToolNotFoundError(
            f"Configured binary '{hint}' does not exist. Update tools.{default_name}.binary "
            f"or REDTEAM_MCP_TOOL_{default_name.upper()} env variable."
        )
    found = shutil.which(default_name)
    if not found:
        raise ToolNotFoundError(
            f"'{default_name}' not found on PATH. Either install it, add it to PATH, "
            f"or set the binary path in config.tools.{default_name}.binary."
        )
    return found


async def run_command(
    argv: Sequence[str],
    *,
    timeout_sec: int = 300,
    max_output_bytes: int = 5 * 1024 * 1024,
    cwd: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
    stdin_data: bytes | None = None,
) -> ExecutionResult:
    """Run ``argv`` as a subprocess with strict resource bounds.

    ``stdin_data`` lets tools feed target lists without writing temp files.
    """

    if not argv:
        raise ValueError("argv must be non-empty")

    effective_env = {**os.environ, **(env or {})}
    _log.debug("exec.start", argv=list(argv), cwd=str(cwd) if cwd else None)

    async def _run() -> ExecutionResult:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.PIPE if stdin_data is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd) if cwd else None,
            env=effective_env,
        )

        async def _drain(stream: asyncio.StreamReader, cap: int) -> tuple[bytes, bool]:
            buf = bytearray()
            truncated = False
            while True:
                chunk = await stream.read(65_536)
                if not chunk:
                    break
                if len(buf) + len(chunk) > cap:
                    remaining = cap - len(buf)
                    if remaining > 0:
                        buf.extend(chunk[:remaining])
                    truncated = True
                    break
                buf.extend(chunk)
            return bytes(buf), truncated

        assert proc.stdout is not None and proc.stderr is not None

        stdin_task: asyncio.Task[None] | None = None
        if stdin_data is not None and proc.stdin is not None:
            async def _feed() -> None:
                assert proc.stdin is not None
                try:
                    proc.stdin.write(stdin_data)
                    await proc.stdin.drain()
                finally:
                    try:
                        proc.stdin.close()
                    except Exception:  # noqa: BLE001
                        pass

            stdin_task = asyncio.create_task(_feed())

        per_stream_cap = max_output_bytes // 2
        stdout_task = asyncio.create_task(_drain(proc.stdout, per_stream_cap))
        stderr_task = asyncio.create_task(_drain(proc.stderr, per_stream_cap))

        exit_code = await proc.wait()
        if stdin_task is not None:
            await stdin_task
        out_bytes, out_truncated = await stdout_task
        err_bytes, err_truncated = await stderr_task

        return ExecutionResult(
            argv=list(argv),
            exit_code=exit_code,
            stdout=out_bytes.decode("utf-8", errors="replace"),
            stderr=err_bytes.decode("utf-8", errors="replace"),
            duration_sec=0.0,
            truncated=out_truncated or err_truncated,
        )

    start = anyio.current_time()
    try:
        with anyio.fail_after(timeout_sec):
            result = await _run()
    except TimeoutError as exc:
        elapsed = anyio.current_time() - start
        raise ExecutionTimeout(
            f"Command exceeded {timeout_sec}s budget: {shlex.join(list(argv))}"
        ) from exc

    result.duration_sec = anyio.current_time() - start
    _log.debug("exec.end", summary=result.summary())
    return result
