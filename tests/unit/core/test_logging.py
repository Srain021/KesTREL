import structlog

from kestrel_mcp import logging as kestrel_logging


def test_structlog_does_not_write_to_stdout(capsys) -> None:
    structlog.reset_defaults()
    kestrel_logging._configured = False

    kestrel_logging.configure_logging(level="INFO", json_mode=True)
    kestrel_logging.get_logger("test").info("mcp.safe_stdio")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert '"event": "mcp.safe_stdio"' in captured.err
