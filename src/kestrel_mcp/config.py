"""Configuration loading for Red-Team MCP.

Layered resolution (later overrides earlier):

    1. Built-in defaults (``config/default.yaml`` shipped with the package)
    2. User config (``~/.kestrel/config.yaml``)
    3. Project config (``$CWD/kestrel.yaml``)
    4. Environment variables prefixed ``KESTREL_MCP_``
    5. ``--config PATH`` CLI override

Config surface is a single :class:`Settings` pydantic model so it can be
shared across server, tools, workflows, tests.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from .features import FeatureFlags

DEFAULT_CONFIG_FILENAME = "default.yaml"
USER_CONFIG_DIR = Path.home() / ".kestrel"
USER_CONFIG_FILE = USER_CONFIG_DIR / "config.yaml"
PROJECT_CONFIG_FILE = Path.cwd() / "kestrel.yaml"


class SecuritySettings(BaseModel):
    """Guard-rails shared by every tool.

    The ``authorized_scope`` list is consulted by any tool that performs an
    outbound action (scan, phish, exploit). A tool marked ``require_scope``
    will refuse to run against a target that doesn't match at least one
    scope entry.

    Scope entries support:
        * exact hostnames        ``example.com``
        * wildcard hostnames     ``*.example.com``
        * CIDR blocks            ``192.168.0.0/16``
        * single IPs             ``10.1.2.3``
    """

    # Typed as Union[list[str], str] so pydantic-settings does NOT attempt
    # to JSON-decode the value when it arrives from an env var. The
    # validator below converts a comma-separated string into a list.
    authorized_scope: list[str] | str = Field(default_factory=list)
    require_ack: bool = True
    dry_run: bool = False
    audit_log: str = "~/.kestrel/audit.log"
    dangerous_ops_require_scope: bool = True

    @field_validator("authorized_scope", mode="after")
    @classmethod
    def _split_scope(cls, v: object) -> list[str]:
        """Normalise scope to a clean ``list[str]``.

        Accepts:
            * a list (straight from YAML)
            * a JSON-encoded list string
            * a comma-separated string (most common for env vars)
        """

        if isinstance(v, list):
            return [str(s).strip() for s in v if str(s).strip()]
        if isinstance(v, str):
            text = v.strip()
            if not text:
                return []
            if text.startswith("[") and text.endswith("]"):
                import json

                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, list):
                        return [str(s).strip() for s in parsed if str(s).strip()]
                except json.JSONDecodeError:
                    pass
            return [s.strip() for s in text.split(",") if s.strip()]
        return []


class ExecutionSettings(BaseModel):
    timeout_sec: int = Field(300, ge=1, le=86_400)
    max_output_bytes: int = Field(5 * 1024 * 1024, ge=1024)
    working_dir: str = "~/.kestrel/runs"


class LoggingSettings(BaseModel):
    level: str = "INFO"
    format: str = "json"
    dir: str = "~/.kestrel/logs"

    @field_validator("level")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class WebUISettings(BaseModel):
    auth_required: bool = False
    username: str = Field(default_factory=lambda: os.getenv("KESTREL_WEB_USER", "kestrel"))
    password_hash: str = ""
    session_cookie_name: str = "kestrel_session"


class ToolBlock(BaseModel):
    """Common shape for every per-tool config block."""

    enabled: bool = False
    binary: str | None = None

    model_config = {"extra": "allow"}


class ToolsSettings(BaseModel):
    model_config = {"extra": "allow"}

    nuclei: ToolBlock = Field(default_factory=lambda: ToolBlock(enabled=True))
    shodan: ToolBlock = Field(default_factory=lambda: ToolBlock(enabled=True))
    subfinder: ToolBlock = Field(default_factory=ToolBlock)
    httpx: ToolBlock = Field(default_factory=ToolBlock)
    nmap: ToolBlock = Field(default_factory=ToolBlock)
    caido: ToolBlock = Field(default_factory=ToolBlock)
    evilginx: ToolBlock = Field(default_factory=ToolBlock)
    sliver: ToolBlock = Field(default_factory=ToolBlock)
    havoc: ToolBlock = Field(default_factory=ToolBlock)
    ligolo: ToolBlock = Field(default_factory=ToolBlock)


class ServerMeta(BaseModel):
    name: str = "kestrel-mcp"
    version: str = "0.1.0"


class Settings(BaseSettings):
    """Top-level configuration object.

    Source precedence is customised so that environment variables override
    init-time kwargs (the latter being used by :func:`load_settings` to
    inject YAML values). The effective order is:

        env > dotenv > secrets > init-kwargs(YAML) > defaults
    """

    model_config = SettingsConfigDict(
        env_prefix="KESTREL_MCP_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    server: ServerMeta = Field(default_factory=ServerMeta)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    execution: ExecutionSettings = Field(default_factory=ExecutionSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    webui: WebUISettings = Field(default_factory=WebUISettings)
    tools: ToolsSettings = Field(default_factory=ToolsSettings)
    edition: Literal["pro", "team"] = Field(default="pro")
    features: FeatureFlags = Field(default_factory=FeatureFlags)

    @classmethod
    def build(cls, edition: str | None = None, **overrides: Any) -> Settings:
        """Build Settings with edition defaults applied before overrides.

        Order of precedence: Pro defaults -> edition defaults -> explicit
        overrides -> env vars (handled by settings_customise_sources).
        """

        from .editions import get_defaults

        ed = edition or os.getenv("KESTREL_EDITION") or overrides.pop("edition", None) or "pro"
        base_features = get_defaults(ed).model_dump()
        user_features = overrides.pop("features", {})
        if isinstance(user_features, FeatureFlags):
            user_features = user_features.model_dump(exclude_unset=True)
        merged = {**base_features, **user_features}
        return cls(edition=ed, features=FeatureFlags(**merged), **overrides)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Put ``env_settings`` ahead of ``init_settings`` so env wins."""

        return (
            env_settings,
            dotenv_settings,
            file_secret_settings,
            init_settings,
        )

    def expanded_path(self, raw: str) -> Path:
        return Path(os.path.expandvars(os.path.expanduser(raw))).resolve()


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file {path} must contain a top-level mapping")
    return data


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_settings(config_path: str | os.PathLike[str] | None = None) -> Settings:
    """Resolve a merged :class:`Settings` instance.

    ``config_path`` (optional) pins a specific YAML file, bypassing the
    user/project search. Precedence (later wins):

        1. Built-in ``config/default.yaml``
        2. ``~/.kestrel/config.yaml`` (or ``config_path`` if given)
        3. ``./kestrel.yaml``
        4. Environment variables prefixed ``KESTREL_MCP_``

    The YAML values are fed to ``Settings(**merged)`` as init kwargs;
    pydantic-settings then overlays ``EnvSettingsSource`` on top
    (env > init > default), which mirrors 12-factor conventions.
    """

    pkg_default = Path(__file__).resolve().parent.parent.parent / "config" / DEFAULT_CONFIG_FILENAME

    merged: dict[str, Any] = {}
    merged = _deep_merge(merged, _read_yaml(pkg_default))

    if config_path is not None:
        merged = _deep_merge(merged, _read_yaml(Path(config_path)))
    else:
        merged = _deep_merge(merged, _read_yaml(USER_CONFIG_FILE))
        merged = _deep_merge(merged, _read_yaml(PROJECT_CONFIG_FILE))

    # IMPORTANT: Use Settings(**merged) — NOT Settings.model_validate(merged) —
    # because the latter bypasses pydantic-settings' EnvSettingsSource, which
    # means KESTREL_MCP_* env vars would never be picked up.
    return Settings(**merged)
