from kestrel_mcp.__main__ import _status_for


def test_impacket_readiness_uses_python_package() -> None:
    status = _status_for("impacket", {"enabled": True}, resolved=None)

    assert "ready" in status
    assert "python module" in status
