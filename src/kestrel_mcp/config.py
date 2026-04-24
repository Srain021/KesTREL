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
from typing import Any, Literal, cast

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from .features import FeatureFlags

DEFAULT_CONFIG_FILENAME = "default.yaml"
USER_CONFIG_DIR = Path.home() / ".kestrel"
USER_CONFIG_FILE = USER_CONFIG_DIR / "config.yaml"
PROJECT_CONFIG_FILE = Path.cwd() / "kestrel.yaml"
EditionName = Literal["pro", "team", "internal"]
_INTERNAL_TOOL_IDS = (
    "nuclei",
    "shodan",
    "subfinder",
    "amass",
    "httpx",
    "katana",
    "nmap",
    "ffuf",
    "sqlmap",
    "impacket",
    "netexec",
    "hashcat",
    "bloodhound",
    "caido",
    "evilginx",
    "sliver",
    "havoc",
    "ligolo",
)


def _normalise_edition(value: object) -> EditionName:
    text = str(value or "pro").strip().lower()
    if text in {"pro", "team", "internal"}:
        return cast("EditionName", text)
    raise ValueError(f"Unknown edition: {value!r}. Expected 'pro', 'team', or 'internal'.")


def _pick_edition(explicit: str | None, configured: object | None = None) -> EditionName:
    raw = (
        os.getenv("KESTREL_MCP_EDITION")
        or os.getenv("KESTREL_EDITION")
        or explicit
        or configured
        or "pro"
    )
    return _normalise_edition(raw)


def _internal_firepower_overlay() -> dict[str, Any]:
    return {"tools": {tool_id: {"enabled": True} for tool_id in _INTERNAL_TOOL_IDS}}


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


class LLMSettings(BaseModel):
    tool_description_mode: Literal["full", "compact"] = "full"
    tool_exposure: Literal["all", "harness_first"] = "all"
    model_tier: Literal["local", "standard", "strong"] = "standard"


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
    amass: ToolBlock = Field(default_factory=ToolBlock)
    httpx: ToolBlock = Field(default_factory=ToolBlock)
    katana: ToolBlock = Field(default_factory=ToolBlock)
    nmap: ToolBlock = Field(default_factory=ToolBlock)
    ffuf: ToolBlock = Field(default_factory=ToolBlock)
    sqlmap: ToolBlock = Field(default_factory=ToolBlock)
    impacket: ToolBlock = Field(default_factory=ToolBlock)
    netexec: ToolBlock = Field(default_factory=ToolBlock)
    hashcat: ToolBlock = Field(default_factory=ToolBlock)
    bloodhound: ToolBlock = Field(default_factory=ToolBlock)
    caido: ToolBlock = Field(default_factory=ToolBlock)
    evilginx: ToolBlock = Field(default_factory=ToolBlock)
    sliver: ToolBlock = Field(default_factory=ToolBlock)
    havoc: ToolBlock = Field(default_factory=ToolBlock)
    ligolo: ToolBlock = Field(default_factory=ToolBlock)


class ServerMeta(BaseModel):
    name: str = "kestrel-mcp"
    version: str = "1.0.0"


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
    execution: ExecutionSettings = Field(
        default_factory=lambda: ExecutionSettings(
            timeout_sec=300,
            max_output_bytes=5 * 1024 * 1024,
            working_dir="~/.kestrel/runs",
        )
    )
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    webui: WebUISettings = Field(default_factory=WebUISettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    tools: ToolsSettings = Field(default_factory=ToolsSettings)
    edition: EditionName = Field(default="pro")
    features: FeatureFlags = Field(default_factory=FeatureFlags)

    @classmethod
    def build(cls, edition: str | None = None, **overrides: Any) -> Settings:
        """Build Settings with edition defaults applied before overrides.

        Order of precedence: Pro defaults -> edition defaults -> explicit
        overrides -> env vars (handled by settings_customise_sources).
        """

        from .editions import get_defaults

        configured_edition = overrides.pop("edition", None)
        ed = _pick_edition(edition, configured_edition)
        base_features = get_defaults(ed).model_dump()
        user_features = overrides.pop("features", {})
        if isinstance(user_features, FeatureFlags):
            user_features = user_features.model_dump(exclude_unset=True)
        merged = {**base_features, **user_features}
        # Back-compat: silently drop feature flags that no longer exist so
        # user config files don't crash on upgrade.
        allowed = set(FeatureFlags.model_fields.keys())
        merged = {k: v for k, v in merged.items() if k in allowed}

        if ed == "internal":
            user_tools = overrides.pop("tools", {})
            if isinstance(user_tools, ToolsSettings):
                user_tools = user_tools.model_dump(exclude_unset=True)
            user_tools_dict = cast("dict[str, Any]", user_tools)
            overrides["tools"] = _deep_merge(
                user_tools_dict,
                _internal_firepower_overlay()["tools"],
            )

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


def load_settings(
    config_path: str | os.PathLike[str] | None = None,
    *,
    edition: str | None = None,
) -> Settings:
    """Resolve a merged :class:`Settings` instance.

    ``config_path`` (optional) pins a specific YAML file, bypassing the
    user/project search. Precedence (later wins):

        1. Built-in ``config/default.yaml``
        2. ``~/.kestrel/config.yaml`` (or ``config_path`` if given)
        3. ``./kestrel.yaml``
        4. Edition overlay (``internal`` enables every bundled tool module)
        5. Environment variables prefixed ``KESTREL_MCP_``

    The YAML values are fed to ``Settings(**merged)`` as init kwargs;
    pydantic-settings then overlays ``EnvSettingsSource`` on top
    (env > init > default), which mirrors 12-factor conventions.
    """

    pkg_default = Path(__file__).resolve().parent.parent.parent / "config" / DEFAULT_CONFIG_FILENAME

    layers: list[dict[str, Any]] = [_read_yaml(pkg_default)]

    if config_path is not None:
        layers.append(_read_yaml(Path(config_path)))
    else:
        layers.append(_read_yaml(USER_CONFIG_FILE))
        layers.append(_read_yaml(PROJECT_CONFIG_FILE))

    probe: dict[str, Any] = {}
    for layer in layers:
        probe = _deep_merge(probe, layer)
    selected_edition = _pick_edition(edition, probe.get("edition"))

    merged: dict[str, Any] = {}
    if layers:
        merged = _deep_merge(merged, layers[0])
    for layer in layers[1:]:
        merged = _deep_merge(merged, layer)
    if selected_edition == "internal":
        merged = _deep_merge(merged, _internal_firepower_overlay())

    # IMPORTANT: Settings.build(...) applies edition presets while
    # pydantic-settings overlays KESTREL_MCP_* env vars during construction.
    merged.pop("edition", None)
    return Settings.build(edition=selected_edition, **merged)
