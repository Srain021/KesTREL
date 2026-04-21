"""Tests for the subprocess executor."""

from __future__ import annotations

import os
import sys

import pytest

from kestrel_mcp.executor import (
    ExecutionTimeout,
    ToolNotFoundError,
    resolve_binary,
    run_command,
)


@pytest.mark.asyncio
async def test_run_command_ok() -> None:
    if sys.platform == "win32":
        argv = ["cmd.exe", "/c", "echo", "hello"]
    else:
        argv = ["/bin/sh", "-c", "echo hello"]
    result = await run_command(argv, timeout_sec=10, max_output_bytes=10_000)
    assert result.ok
    assert "hello" in result.stdout


@pytest.mark.asyncio
async def test_run_command_non_zero_exit() -> None:
    if sys.platform == "win32":
        argv = ["cmd.exe", "/c", "exit", "3"]
    else:
        argv = ["/bin/sh", "-c", "exit 3"]
    result = await run_command(argv, timeout_sec=10, max_output_bytes=10_000)
    assert not result.ok
    assert result.exit_code == 3


@pytest.mark.asyncio
async def test_run_command_output_cap() -> None:
    if sys.platform == "win32":
        argv = ["cmd.exe", "/c", "for /L %i in (1,1,5000) do @echo aaaaaaaaaa"]
    else:
        argv = ["/bin/sh", "-c", "for i in $(seq 1 5000); do echo aaaaaaaaaa; done"]
    result = await run_command(argv, timeout_sec=30, max_output_bytes=512)
    assert result.truncated


@pytest.mark.asyncio
async def test_run_command_timeout() -> None:
    if sys.platform == "win32":
        argv = ["cmd.exe", "/c", "ping", "-n", "5", "127.0.0.1"]
    else:
        argv = ["/bin/sh", "-c", "sleep 5"]
    with pytest.raises(ExecutionTimeout):
        await run_command(argv, timeout_sec=1, max_output_bytes=10_000)


@pytest.mark.asyncio
async def test_run_command_with_stdin() -> None:
    if sys.platform == "win32":
        pytest.skip("`cat` not reliably available on Windows runners")
    argv = ["/bin/cat"]
    result = await run_command(
        argv, timeout_sec=10, max_output_bytes=10_000, stdin_data=b"piped input"
    )
    assert "piped input" in result.stdout


def test_resolve_binary_from_path() -> None:
    name = "cmd" if sys.platform == "win32" else "sh"
    found = resolve_binary(None, name)
    assert os.path.isabs(found)


def test_resolve_binary_missing_raises() -> None:
    with pytest.raises(ToolNotFoundError):
        resolve_binary(None, "__definitely_not_on_path__")


def test_resolve_binary_hint_nonexistent_raises() -> None:
    with pytest.raises(ToolNotFoundError):
        resolve_binary("/nope/not-here/tool", "some_tool")
