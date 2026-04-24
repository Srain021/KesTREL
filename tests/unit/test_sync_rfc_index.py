from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_sync_module():
    path = Path(__file__).resolve().parents[2] / "scripts" / "sync_rfc_index.py"
    spec = importlib.util.spec_from_file_location("sync_rfc_index_for_test", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_sync_markers_must_be_standalone_lines(tmp_path: Path, monkeypatch) -> None:
    sync = _load_sync_module()
    index = tmp_path / "INDEX.md"
    original = (
        "# RFC INDEX\n\n"
        "Mention <!-- BEGIN_RFC_TABLE --> and <!-- END_RFC_TABLE --> inline only.\n"
    )
    index.write_text(original, encoding="utf-8")
    monkeypatch.setattr(sync, "INDEX_PATH", index)

    changed = sync.apply_to_index("rendered", dry_run=False)

    assert changed is False
    assert index.read_text(encoding="utf-8") == original


def test_sync_replaces_standalone_marker_region(tmp_path: Path, monkeypatch) -> None:
    sync = _load_sync_module()
    index = tmp_path / "INDEX.md"
    index.write_text(
        "# RFC INDEX\n\n"
        "<!-- BEGIN_RFC_TABLE -->\n"
        "old\n"
        "<!-- END_RFC_TABLE -->\n"
        "\nfooter\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sync, "INDEX_PATH", index)

    changed = sync.apply_to_index("new table", dry_run=False)

    assert changed is True
    assert "<!-- BEGIN_RFC_TABLE -->\nnew table\n<!-- END_RFC_TABLE -->" in index.read_text(
        encoding="utf-8"
    )


def test_epic_aliases_normalize_legacy_front_matter(tmp_path: Path) -> None:
    sync = _load_sync_module()
    path = tmp_path / "RFC-V13-demo.md"
    path.write_text(
        "---\n"
        "id: RFC-V13\n"
        "title: Demo\n"
        "epic: V-Cross-edition\n"
        "status: done\n"
        "blocking_on: []\n"
        "owner: agent\n"
        "---\n"
        "\n# Demo\n",
        encoding="utf-8",
    )

    entry = sync.parse_rfc(path)

    assert entry is not None
    assert entry.epic == "V-CrossEdition"
