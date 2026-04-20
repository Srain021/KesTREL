"""Tests for RFC-T08 team bootstrap command."""

from __future__ import annotations

from pathlib import Path

from redteam_mcp.team.bootstrap import BootstrapReport, bootstrap


def test_dry_run_reports_no_mutation(tmp_path, monkeypatch):
    # Point KESTREL_DATA_DIR at an isolated tmp so nothing real is touched.
    monkeypatch.setenv("KESTREL_DATA_DIR", str(tmp_path))
    report = bootstrap(name="op-test", scope="a.com,b.net", dry_run=True)

    assert report.dry_run is True
    assert report.engagement_id is None
    assert report.scope_added == ["a.com", "b.net"]
    assert report.edition == "team"
    # Dry-run must NOT create the sqlite file.
    assert not (tmp_path / "data.db").exists()


def test_report_render_contains_expected_sections():
    r = BootstrapReport(
        name="op-x",
        edition="team",
        data_dir=Path("/tmp/x"),
        dry_run=True,
        scope_added=["a.com"],
    )
    text = r.render()
    assert "Kestrel Team Edition" in text
    assert "op-x" in text
    assert "Next steps" in text
    assert "kestrel --edition team" in text
    assert "a.com" in text


def test_report_render_handles_empty_scope_and_warnings():
    r = BootstrapReport(
        name="op-y",
        edition="team",
        data_dir=Path("/tmp/y"),
        dry_run=False,
        doctor_warnings=["nuclei not on PATH"],
    )
    text = r.render()
    assert "Doctor warnings" in text
    assert "nuclei" in text


def test_real_bootstrap_creates_engagement(tmp_path, monkeypatch):
    """Non-dry-run: actually creates sqlite + Engagement."""
    monkeypatch.setenv("KESTREL_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("KESTREL_EDITION", raising=False)

    report = bootstrap(
        name="op-real",
        scope="example.com,target.lab",
        dry_run=False,
    )

    assert report.engagement_id is not None
    assert len(report.engagement_id) >= 32  # UUID string
    assert set(report.scope_added) == {"example.com", "target.lab"}
    # Verify sqlite file exists after.
    assert (tmp_path / "data.db").exists()


def test_empty_scope_still_creates_engagement(tmp_path, monkeypatch):
    monkeypatch.setenv("KESTREL_DATA_DIR", str(tmp_path))
    report = bootstrap(name="op-z", scope=None, dry_run=False)
    assert report.engagement_id is not None
    assert report.scope_added == []


def test_bootstrap_respects_pro_edition_when_forced(tmp_path, monkeypatch):
    """Sanity: if caller passes edition='pro', the report reflects pro."""
    monkeypatch.setenv("KESTREL_DATA_DIR", str(tmp_path))
    report = bootstrap(name="op-pro", dry_run=True, edition="pro")
    assert report.edition == "pro"
