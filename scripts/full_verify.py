"""End-to-end verification of every subsystem.

Runs eight independent checks and prints a single pass/fail matrix.
Exits non-zero if ANY check fails.
"""

from __future__ import annotations

import ast
import asyncio
import importlib
import json
import os
import pathlib
import subprocess
import tempfile
import time
from collections.abc import Callable

REPO = pathlib.Path(__file__).resolve().parent.parent


def _venv_executable(name: str) -> pathlib.Path:
    bin_dir = "Scripts" if os.name == "nt" else "bin"
    suffix = ".exe" if os.name == "nt" else ""
    return REPO / ".venv" / bin_dir / f"{name}{suffix}"


VENV_PYTHON = _venv_executable("python")


class Check:
    __slots__ = ("name", "ok", "detail", "elapsed")

    def __init__(self, name: str, ok: bool, detail: str, elapsed: float) -> None:
        self.name = name
        self.ok = ok
        self.detail = detail
        self.elapsed = elapsed


def time_it(name: str, fn: Callable[[], tuple[bool, str]]) -> Check:
    start = time.perf_counter()
    try:
        ok, detail = fn()
    except Exception as exc:  # noqa: BLE001
        ok, detail = False, f"{type(exc).__name__}: {exc}"
    return Check(name, ok, detail, time.perf_counter() - start)


def check_syntax() -> tuple[bool, str]:
    root = REPO
    py_files = [
        p for p in root.rglob("*.py")
        if "__pycache__" not in p.parts and ".venv" not in p.parts
    ]
    broken: list[str] = []
    for p in py_files:
        try:
            ast.parse(p.read_text("utf-8"))
        except SyntaxError as exc:
            broken.append(f"{p.relative_to(root)}: {exc}")
    return (not broken, f"{len(py_files)} files, {len(broken)} broken")


def check_imports() -> tuple[bool, str]:
    modules = [
        "kestrel_mcp",
        "kestrel_mcp.config",
        "kestrel_mcp.logging",
        "kestrel_mcp.security",
        "kestrel_mcp.executor",
        "kestrel_mcp.server",
        "kestrel_mcp.tools",
        "kestrel_mcp.tools.base",
        "kestrel_mcp.tools.shodan_tool",
        "kestrel_mcp.tools.nuclei_tool",
        "kestrel_mcp.tools.caido_tool",
        "kestrel_mcp.tools.ligolo_tool",
        "kestrel_mcp.tools.sliver_tool",
        "kestrel_mcp.tools.havoc_tool",
        "kestrel_mcp.tools.evilginx_tool",
        "kestrel_mcp.workflows",
        "kestrel_mcp.workflows.recon",
        "kestrel_mcp.workflows.report",
        "kestrel_mcp.parsers",
        "kestrel_mcp.resources",
        "kestrel_mcp.prompts",
    ]
    broken: list[str] = []
    for m in modules:
        try:
            importlib.import_module(m)
        except Exception as exc:  # noqa: BLE001
            broken.append(f"{m}: {exc}")
    return (not broken, f"{len(modules) - len(broken)}/{len(modules)} modules")


def check_tests() -> tuple[bool, str]:
    command = [str(VENV_PYTHON), "-m", "pytest", "tests/", "-q", "--no-header"]
    try:
        res = subprocess.run(command, cwd=str(REPO), stdin=subprocess.DEVNULL, timeout=180)
    except subprocess.TimeoutExpired:
        return False, "pytest timed out after 180s"
    return (res.returncode == 0, f"pytest exit={res.returncode}")


def _run_cli(args: list[str], extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Run the CLI with UTF-8 output so rich's box characters don't choke cp1252/gbk."""

    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [str(VENV_PYTHON), "-m", "kestrel_mcp", *args],
        capture_output=True,
        cwd=str(REPO),
        env=env,
        encoding="utf-8",
        errors="replace",
    )


def check_cli_version() -> tuple[bool, str]:
    res = _run_cli(["version"])
    out = (res.stdout or "").strip()
    return (res.returncode == 0 and out.count(".") == 2, f"version={out!r}")


def check_cli_doctor() -> tuple[bool, str]:
    res = _run_cli(["doctor"])
    combined = (res.stdout or "") + (res.stderr or "")
    has_table = "Tool" in combined and ("Status" in combined or "Binary" in combined)
    ok = res.returncode == 0 and has_table
    return (ok, f"exit={res.returncode}, table_rendered={has_table}")


def check_cli_list_tools() -> tuple[bool, str]:
    extra = {
        "KESTREL_MCP_TOOLS__CAIDO__ENABLED": "true",
        "KESTREL_MCP_TOOLS__EVILGINX__ENABLED": "true",
        "KESTREL_MCP_TOOLS__SLIVER__ENABLED": "true",
        "KESTREL_MCP_TOOLS__HAVOC__ENABLED": "true",
        "KESTREL_MCP_TOOLS__LIGOLO__ENABLED": "true",
        "KESTREL_MCP_SECURITY__AUTHORIZED_SCOPE": "*.lab.test",
    }
    res = _run_cli(["list-tools"], extra)
    if res.returncode != 0:
        return (False, f"exit={res.returncode}")
    tools = json.loads(res.stdout)
    modules = {t["module"] for t in tools}
    # Check that at least one tool has the new rich-description fields
    rich = [t for t in tools if t.get("when_to_use")]
    return (
        len(tools) >= 41 and len(modules) >= 8 and len(rich) >= 6,
        f"{len(tools)} tools across {len(modules)} modules; {len(rich)} with rich guidance",
    )


async def _mcp_handler_roundtrip() -> tuple[bool, str]:
    """Exercise an in-process tool dispatch through the MCP server wiring."""

    from kestrel_mcp.config import load_settings
    from kestrel_mcp.server import RedTeamMCPServer

    settings = load_settings()
    server = RedTeamMCPServer(settings)
    report = server._specs["generate_pentest_report"]
    result = await report.handler(
        {
            "title": "Verification",
            "scope": "*.lab.test",
            "findings": [
                {"title": "Test", "severity": "info", "target": "127.0.0.1"},
            ],
        }
    )
    if result.is_error:
        return False, f"tool returned error: {result.text[:80]}"
    if "Verification" not in result.text:
        return False, "missing title in rendered report"
    if not result.structured or "markdown" not in result.structured:
        return False, "no structured markdown output"
    return True, f"{len(server._specs)} specs registered, roundtrip {len(result.text)}B"


def check_mcp_roundtrip() -> tuple[bool, str]:
    return asyncio.run(_mcp_handler_roundtrip())


def check_scope_guard() -> tuple[bool, str]:
    from kestrel_mcp.security import AuthorizationError, ScopeGuard

    # 1. Empty scope denies
    empty = ScopeGuard([])
    try:
        empty.ensure("example.com", tool_name="x")
        return False, "empty scope should deny"
    except AuthorizationError:
        pass

    # 2. Wildcard
    g = ScopeGuard(["*.lab.test", "10.0.0.0/8"])
    g.ensure("sub.lab.test", tool_name="x")
    g.ensure("https://api.lab.test/v1", tool_name="x")
    g.ensure("10.1.2.3", tool_name="x")

    # 3. Denies out of scope
    try:
        g.ensure("evil.com", tool_name="x")
        return False, "out-of-scope target should be denied"
    except AuthorizationError:
        pass

    return True, "empty-deny + wildcard + CIDR + out-of-scope deny all verified"


def main() -> int:
    if not VENV_PYTHON.is_file():
        print(f"FATAL: venv not found at {VENV_PYTHON}")
        return 2

    checks: list[Check] = [
        time_it("1. Python syntax (all source)", check_syntax),
        time_it("2. All 21 modules importable", check_imports),
        time_it("3. CLI: version", check_cli_version),
        time_it("4. CLI: doctor renders table", check_cli_doctor),
        time_it("5. CLI: list-tools returns 41+", check_cli_list_tools),
        time_it("6. In-process MCP handler roundtrip", check_mcp_roundtrip),
        time_it("7. ScopeGuard enforcement", check_scope_guard),
        time_it("8. Full test suite passes", check_tests),
    ]

    print()
    print("=" * 74)
    print(f"{'CHECK':<45} {'TIME':>8} {'STATUS':>8}  DETAIL")
    print("-" * 74)
    passed = 0
    for c in checks:
        mark = "PASS" if c.ok else "FAIL"
        if c.ok:
            passed += 1
        print(f"{c.name:<45} {c.elapsed:>6.2f}s {mark:>8}  {c.detail}")
    print("=" * 74)
    total = len(checks)
    print(f"Result: {passed}/{total} checks passed.")
    print()

    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
