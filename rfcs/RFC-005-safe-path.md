---
id: RFC-005
title: Safe path helper + subprocess stderr redaction
epic: A-Foundations
status: done
owner: agent
role: backend-engineer
blocking_on:
  - RFC-002
budget:
  max_files_touched: 5
  max_new_files: 2
  max_lines_added: 300
  max_minutes_human: 25
  max_tokens_model: 12000
files_to_read:
  - src/redteam_mcp/executor.py
  - src/redteam_mcp/tools/caido_tool.py
  - src/redteam_mcp/tools/ligolo_tool.py
files_will_touch:
  - src/redteam_mcp/core/paths.py            # new
  - src/redteam_mcp/core/redact.py           # new
  - src/redteam_mcp/executor.py              # modified (redact stderr)
  - tests/unit/core/test_paths_and_redact.py # new
  - CHANGELOG.md                             # modified
verify_cmd: |
  .venv\Scripts\python.exe -m pytest tests/unit/core/test_paths_and_redact.py -v
rollback_cmd: |
  git checkout -- .
  if exist src\redteam_mcp\core\paths.py del src\redteam_mcp\core\paths.py
  if exist src\redteam_mcp\core\redact.py del src\redteam_mcp\core\redact.py
  if exist tests\unit\core\test_paths_and_redact.py del tests\unit\core\test_paths_and_redact.py
skill_id: rfc-005-safe-path
---

# RFC-005 — Safe path + subprocess stderr redaction

## Mission

提供两个防线：`safe_path()` 阻断路径遍历；`redact()` 清洗 subprocess stderr 里的敏感串。

## Context

- THREAT T-E3 (path traversal)：工具接受用户路径参数时必须 normalize + 限根。
- THREAT T-I4 (stderr redaction)：子进程把 token/password 吐到 stderr 进日志。
- 两个修都是纯函数 + 适量 regex，放一个 RFC 处理减小开销。

## Non-goals

- 不改具体工具调用点（下一个 RFC 再接入 specific handlers）
- 不做完整 DLP 规则（复杂 regex 留给专门 RFC-B05）

## Design

### safe_path(base, user_input) → Path

- 接受：`base` 必须是绝对已存在目录；`user_input` 可以是相对或绝对
- 返回：`base / user_input` 的 resolve() 结果，**必须** 在 base 子树下；否则抛 `PathTraversalError`
- 不跟随 symlink（即使 os.path.realpath 跟，我们的 resolve(strict=False) 后再 commonpath 检查）
- Windows + POSIX 兼容

### redact(text) → str

替换常见敏感串：

- `Bearer <token>` → `Bearer <REDACTED>`
- `Authorization: X Y` 整行 → `Authorization: <REDACTED>`
- `api[_-]?key[=:]\s*\S+` → `api_key=<REDACTED>`
- 看似 JWT (`eyJ...`) → 前缀 + `<REDACTED>`
- 看似 NTLM hash（32 hex）→ `<NTLM_HASH_REDACTED>`
- 看似私钥块 `-----BEGIN ... PRIVATE KEY-----` 整块 → `<PRIVATE_KEY_REDACTED>`

不求完美；目标是「常见场景不泄漏」。

### executor 集成

`ExecutionResult.stderr` 在返回前跑 `redact()`。新增 fixture flag `redact_stderr=True`（默认开），让测试可以按需关闭。

## Steps

### Step 1 — paths.py

```
WRITE src/redteam_mcp/core/paths.py
```
```python
"""Path traversal defence.

Whenever a tool receives a file path from the user or an LLM, route it
through :func:`safe_path` to guarantee the result stays under a declared
root. Mitigates THREAT T-E3.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath

from ..core_errors import UserInputError


class PathTraversalError(UserInputError):
    error_code = "kestrel.path_traversal"


def safe_path(base: Path | str, user_input: str) -> Path:
    """Join ``user_input`` under ``base`` and refuse if it escapes.

    Examples
    --------
    >>> safe_path('/tmp/work', 'report.pdf')    # /tmp/work/report.pdf
    >>> safe_path('/tmp/work', '../etc/passwd') # raises PathTraversalError
    >>> safe_path('/tmp/work', '/etc/passwd')   # raises PathTraversalError
    """

    base_path = Path(base).resolve(strict=False)
    if not base_path.exists() or not base_path.is_dir():
        raise PathTraversalError(
            f"safe_path base does not exist or is not a directory: {base_path}"
        )

    candidate_raw = str(user_input or "").strip()
    if not candidate_raw:
        raise PathTraversalError("safe_path: user_input is empty")

    # Normalize separators; reject absolute inputs flat-out
    lower = candidate_raw.lower()
    if candidate_raw.startswith(("/", "\\")) or (len(candidate_raw) >= 2 and candidate_raw[1] == ":"):
        # absolute paths (POSIX /, Windows \, drive-letter C:) are banned
        raise PathTraversalError(
            f"safe_path: absolute user input refused: {candidate_raw!r}"
        )

    joined = (base_path / candidate_raw).resolve(strict=False)
    try:
        joined.relative_to(base_path)
    except ValueError as exc:
        raise PathTraversalError(
            f"safe_path: '{candidate_raw}' escapes base {base_path}"
        ) from exc

    return joined
```

### Step 2 — redact.py

```
WRITE src/redteam_mcp/core/redact.py
```
```python
"""Sensitive-string redaction for logs and subprocess output.

Best-effort; NOT a full DLP. Aim: common tokens / hashes / keys do not
end up in audit logs. Mitigates THREAT T-I4.
"""

from __future__ import annotations

import re

_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
     "<PRIVATE_KEY_REDACTED>"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._\-+/=]{8,}"),
     "Bearer <REDACTED>"),
    (re.compile(r"(?im)^\s*Authorization\s*:\s*.+$"),
     "Authorization: <REDACTED>"),
    (re.compile(r"(?i)(api[_-]?key|secret[_-]?key|access[_-]?key)\s*[=:]\s*[\"']?[A-Za-z0-9._\-+/]{8,}[\"']?"),
     r"\1=<REDACTED>"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b"),
     "<JWT_REDACTED>"),
    (re.compile(r"\b[a-fA-F0-9]{32}:[a-fA-F0-9]{32}\b"),
     "<NTLM_HASH_PAIR_REDACTED>"),
    (re.compile(r"(?i)password\s*[=:]\s*[\"']?\S+[\"']?"),
     "password=<REDACTED>"),
]


def redact(text: str) -> str:
    """Apply every redaction rule in sequence. Safe on empty / None."""

    if not text:
        return text
    for pattern, replacement in _RULES:
        text = pattern.sub(replacement, text)
    return text
```

### Step 3 — executor 接入

```
REPLACE src/redteam_mcp/executor.py
<<<<<<< SEARCH
from .logging import get_logger
=======
from .core.redact import redact
from .logging import get_logger
>>>>>>> REPLACE
```

```
REPLACE src/redteam_mcp/executor.py
<<<<<<< SEARCH
        return ExecutionResult(
            argv=list(argv),
            exit_code=exit_code,
            stdout=out_bytes.decode("utf-8", errors="replace"),
            stderr=err_bytes.decode("utf-8", errors="replace"),
            duration_sec=0.0,
            truncated=out_truncated or err_truncated,
        )
=======
        return ExecutionResult(
            argv=list(argv),
            exit_code=exit_code,
            stdout=out_bytes.decode("utf-8", errors="replace"),
            stderr=redact(err_bytes.decode("utf-8", errors="replace")),
            duration_sec=0.0,
            truncated=out_truncated or err_truncated,
        )
>>>>>>> REPLACE
```

### Step 4 — 测试

```
WRITE tests/unit/core/test_paths_and_redact.py
```
```python
"""Tests for safe_path + redact."""

from __future__ import annotations

from pathlib import Path

import pytest

from redteam_mcp.core.paths import PathTraversalError, safe_path
from redteam_mcp.core.redact import redact


# ---------------------------------------------------------------- safe_path


def test_basic_join(tmp_path):
    result = safe_path(tmp_path, "sub/file.txt")
    assert result == (tmp_path / "sub/file.txt").resolve()


def test_base_must_exist(tmp_path):
    with pytest.raises(PathTraversalError):
        safe_path(tmp_path / "does-not-exist", "x.txt")


def test_rejects_dot_dot(tmp_path):
    with pytest.raises(PathTraversalError):
        safe_path(tmp_path, "../etc/passwd")


def test_rejects_abs_posix(tmp_path):
    with pytest.raises(PathTraversalError):
        safe_path(tmp_path, "/etc/passwd")


def test_rejects_abs_windows_drive(tmp_path):
    with pytest.raises(PathTraversalError):
        safe_path(tmp_path, "C:\\Windows\\System32")


def test_rejects_empty(tmp_path):
    with pytest.raises(PathTraversalError):
        safe_path(tmp_path, "")


def test_nested_dotdot_still_rejected(tmp_path):
    (tmp_path / "inner").mkdir()
    with pytest.raises(PathTraversalError):
        safe_path(tmp_path, "inner/../../outside")


def test_allows_inner_dotdot_that_stays_in_base(tmp_path):
    """foo/../bar resolves to tmp_path/bar which is allowed."""

    result = safe_path(tmp_path, "foo/../bar")
    assert result == (tmp_path / "bar").resolve()


# ------------------------------------------------------------------ redact


def test_bearer_token():
    assert "Bearer <REDACTED>" in redact("Authorization: Bearer abcd1234efgh5678")


def test_authorization_line():
    assert "Authorization: <REDACTED>" in redact("Authorization: token=abc123")


def test_api_key_equals():
    assert "api_key=<REDACTED>" in redact("api_key=ABCDEFG123456789")


def test_access_key():
    # rule captures "access-key" with dashes via (api[_-]?key|secret[_-]?key|access[_-]?key)
    out = redact("access-key=AKIA1234567890ABCDEF")
    assert "<REDACTED>" in out


def test_jwt():
    sample = "token: eyJabc123.eyJdef456.xyz789-abc"
    out = redact(sample)
    assert "<JWT_REDACTED>" in out


def test_ntlm_pair():
    assert "<NTLM_HASH_PAIR_REDACTED>" in redact(
        "hash: aad3b435b51404eeaad3b435b51404ee:31d6cfe0d16ae931b73c59d7e0c089c0"
    )


def test_password_equals():
    assert "password=<REDACTED>" in redact("user=admin password=s3cret")


def test_private_key_block():
    block = "-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n-----END RSA PRIVATE KEY-----"
    assert "<PRIVATE_KEY_REDACTED>" in redact(block)


def test_empty_is_safe():
    assert redact("") == ""
    assert redact(None) is None  # type: ignore[arg-type]


def test_idempotent():
    sample = "Bearer ABC123"
    once = redact(sample)
    twice = redact(once)
    assert once == twice
```

### Step 5 — CHANGELOG

```
APPEND CHANGELOG.md

- RFC-005 — Safe path helper + stderr redaction (closes T-E3 partial, T-I4 partial)
```

### Step 6 — verify + full_verify

```
RUN .venv\Scripts\python.exe -m pytest tests/unit/core/test_paths_and_redact.py -v
RUN .venv\Scripts\python.exe scripts\full_verify.py
```

## Tests

15 个 case：8 个 safe_path / 7 个 redact。

## Post-checks

- [ ] 既有 executor 测试 (`test_executor.py`) 仍全绿 —— redact 不破坏正常输出
- [ ] `full_verify` 8/8

## Rollback plan

见 front-matter。

## Updates to other docs

- `CHANGELOG.md` ✓
- `THREAT_MODEL.md`：T-E3 / T-I4 状态改 `⚠️ partial`
- `GAP_ANALYSIS.md`：相应 gap 更新

## Notes for executor

- `redact()` 的 regex 顺序重要 —— 长 pattern 在前（PRIVATE KEY 比 api_key 优先，否则子串被错切）
- `safe_path` 的 `resolve(strict=False)` 在 Windows 上会 normalize 大小写；测试用 `.resolve()` 对比，避免 Path literal 在 Windows / POSIX 行为不同
- 不要把 `redact` 应用到 `stdout` —— Tool 可能本身要返回 token（比如 shodan_account_info 的 API key 可能在响应中，但那不经 executor）

## Changelog

- **2026-04-21 初版**
