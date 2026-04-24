"""Central error taxonomy for the entire kestrel-mcp codebase.

Addresses GAP G-E1 in GAP_ANALYSIS.md.

Hierarchy:

    KestrelError
    ├── UserInputError              (4xx, user-fixable)
    ├── AuthorizationError          (403)
    ├── ToolNotFoundError           (500, config/install)
    ├── ToolExecutionError          (500, subprocess failed)
    ├── ExternalServiceError        (502, Shodan/upstream API failed)
    ├── InternalError               (500, bug)
    └── DomainError                 (base for domain/errors.py)

Every exception carries:

    error_code          stable string key for programmatic handling
    user_actionable     True if the message tells the user how to fix it
    http_like_status    maps to REST layer or doc-string MCP status

Rendered consistently to ToolResult by the server, and later to HTTP
responses by FastAPI exception handlers.
"""

from __future__ import annotations


class KestrelError(Exception):
    """Root of all kestrel-raised exceptions."""

    error_code: str = "kestrel.generic"
    user_actionable: bool = False
    http_like_status: int = 500

    def __init__(self, message: str = "", **context: object) -> None:
        super().__init__(message)
        self.context: dict[str, object] = dict(context)

    def as_dict(self) -> dict[str, object]:
        return {
            "error_code": self.error_code,
            "message": str(self),
            "user_actionable": self.user_actionable,
            "http_like_status": self.http_like_status,
            "context": self.context,
        }


class UserInputError(KestrelError):
    error_code = "kestrel.user_input"
    user_actionable = True
    http_like_status = 400


class AuthorizationError(KestrelError):
    """Existing alias kept for backward compatibility with security.py."""

    error_code = "kestrel.authorization"
    user_actionable = True
    http_like_status = 403


class ToolNotFoundError(KestrelError):
    error_code = "kestrel.tool_not_found"
    user_actionable = True
    http_like_status = 500


class ToolExecutionError(KestrelError):
    error_code = "kestrel.tool_execution"
    http_like_status = 500


class ExternalServiceError(KestrelError):
    error_code = "kestrel.external_service"
    http_like_status = 502


class InternalError(KestrelError):
    error_code = "kestrel.internal"
    http_like_status = 500
