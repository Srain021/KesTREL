from __future__ import annotations

from pathlib import Path

import pytest

from kestrel_mcp.config import Settings
from kestrel_mcp.executor import ExecutionResult
from kestrel_mcp.security import ScopeGuard
from kestrel_mcp.tools.hashcat_tool import HashcatModule, _parse_hashcat_outfile

pytestmark = pytest.mark.asyncio


def _module(tmp_path: Path) -> HashcatModule:
    words = tmp_path / "words"
    words.mkdir()
    (words / "rockyou.txt").write_text("Password1!\n", encoding="utf-8")
    hashes = tmp_path / "hashes"
    hashes.mkdir()
    return HashcatModule(
        Settings(
            tools={
                "hashcat": {
                    "enabled": True,
                    "binary": "hashcat",
                    "wordlists_dir": str(words),
                    "hashes_dir": str(hashes),
                }
            }
        ),
        ScopeGuard([]),
    )


def _spec(module: HashcatModule, name: str):
    return next(s for s in module.specs() if s.name == name)


async def test_hashcat_crack_returns_detailed_plaintext(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_run_command(*args, **kwargs):  # noqa: ANN002, ANN003
        argv = list(args[0])
        outfile = Path(argv[argv.index("--outfile") + 1])
        outfile.write_text("8846f7eaee8fb117ad06bdd830b7586c:Password1!\n", encoding="utf-8")
        return ExecutionResult(
            argv=argv, exit_code=0, stdout="Recovered", stderr="", duration_sec=0.1
        )

    monkeypatch.setattr("kestrel_mcp.tools.hashcat_tool.resolve_binary", lambda *_: "hashcat")
    monkeypatch.setattr("kestrel_mcp.tools.hashcat_tool.run_command", fake_run_command)
    result = await _spec(_module(tmp_path), "hashcat_crack").handler(
        {
            "hash_mode": 1000,
            "attack_mode": 0,
            "hashes": ["8846f7eaee8fb117ad06bdd830b7586c"],
            "wordlist": "rockyou.txt",
        }
    )

    assert not result.is_error
    assert result.structured["cracked"][0]["plaintext"] == "Password1!"
    assert result.structured["cracked"][0]["hash"] == "8846f7eaee8fb117ad06bdd830b7586c"


async def test_hashcat_requires_one_hash_source(tmp_path: Path) -> None:
    result = await _spec(_module(tmp_path), "hashcat_crack").handler(
        {"hash_mode": 1000, "attack_mode": 3, "mask": "?a"}
    )
    assert result.is_error


async def test_parse_hashcat_outfile() -> None:
    assert _parse_hashcat_outfile("hash:plain\n") == [{"hash": "hash", "plaintext": "plain"}]
