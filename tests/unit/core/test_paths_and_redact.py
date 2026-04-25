"""Tests for safe_path and subprocess-output redaction."""

from __future__ import annotations

import sys

import pytest

from kestrel_mcp.core.paths import PathTraversalError, safe_path
from kestrel_mcp.core.redact import redact
from kestrel_mcp.executor import run_command


def test_safe_path_basic_join(tmp_path):
    result = safe_path(tmp_path, "sub/file.txt")
    assert result == (tmp_path / "sub/file.txt").resolve()


def test_safe_path_base_must_exist(tmp_path):
    with pytest.raises(PathTraversalError):
        safe_path(tmp_path / "does-not-exist", "x.txt")


def test_safe_path_rejects_dot_dot(tmp_path):
    with pytest.raises(PathTraversalError):
        safe_path(tmp_path, "../etc/passwd")


def test_safe_path_rejects_abs_posix(tmp_path):
    with pytest.raises(PathTraversalError):
        safe_path(tmp_path, "/etc/passwd")


def test_safe_path_rejects_abs_windows_drive(tmp_path):
    with pytest.raises(PathTraversalError):
        safe_path(tmp_path, "C:\\Windows\\System32")


def test_safe_path_rejects_empty(tmp_path):
    with pytest.raises(PathTraversalError):
        safe_path(tmp_path, "")


def test_safe_path_nested_dotdot_still_rejected(tmp_path):
    (tmp_path / "inner").mkdir()
    with pytest.raises(PathTraversalError):
        safe_path(tmp_path, "inner/../../outside")


def test_safe_path_allows_inner_dotdot_that_stays_in_base(tmp_path):
    result = safe_path(tmp_path, "foo/../bar")
    assert result == (tmp_path / "bar").resolve()


def test_redact_bearer_token():
    assert "Bearer <REDACTED>" in redact("Bearer abcd1234efgh5678")


def test_redact_authorization_line():
    assert "Authorization: <REDACTED>" in redact("Authorization: token=abc123")


def test_redact_api_key_equals():
    assert "api_key=<REDACTED>" in redact("api_key=ABCDEFG123456789")


def test_redact_access_key():
    out = redact("access-key=AKIA1234567890ABCDEF")
    assert "access-key=<REDACTED>" in out


def test_redact_jwt():
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI.eyJzdWIiOiIxMjM0NTY3ODkw.signature12345"
    assert "<JWT_REDACTED>" in redact(f"token: {token}")


def test_redact_ntlm_pair():
    out = redact("hash: aad3b435b51404eeaad3b435b51404ee:31d6cfe0d16ae931b73c59d7e0c089c0")
    assert "<NTLM_HASH_PAIR_REDACTED>" in out


def test_redact_password_equals():
    assert "password=<REDACTED>" in redact("user=admin password=s3cret")


def test_redact_private_key_block():
    block = "-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n-----END RSA PRIVATE KEY-----"
    assert "<PRIVATE_KEY_REDACTED>" in redact(block)


def test_redact_empty_and_none_are_safe():
    assert redact("") == ""
    assert redact(None) is None


def test_redact_idempotent():
    sample = "Bearer ABC123456789"
    assert redact(redact(sample)) == redact(sample)


@pytest.mark.asyncio
async def test_run_command_redacts_stderr_by_default():
    if sys.platform == "win32":
        argv = ["cmd.exe", "/c", "echo api_key=ABCDEFG123456789 1>&2"]
    else:
        argv = ["/bin/sh", "-c", "echo 'api_key=ABCDEFG123456789' >&2"]

    result = await run_command(argv, timeout_sec=10, max_output_bytes=10_000)

    assert "api_key=<REDACTED>" in result.stderr
    assert "ABCDEFG123456789" not in result.stderr


@pytest.mark.asyncio
async def test_run_command_can_disable_stderr_redaction():
    if sys.platform == "win32":
        argv = ["cmd.exe", "/c", "echo api_key=ABCDEFG123456789 1>&2"]
    else:
        argv = ["/bin/sh", "-c", "echo 'api_key=ABCDEFG123456789' >&2"]

    result = await run_command(
        argv,
        timeout_sec=10,
        max_output_bytes=10_000,
        redact_stderr=False,
    )

    assert "api_key=ABCDEFG123456789" in result.stderr
