"""BloodHound-CE REST client wrapper."""

from __future__ import annotations

from typing import Any

import httpx

from ..config import Settings
from ..logging import audit_event
from ..security import ScopeGuard
from .base import ToolModule, ToolResult, ToolSpec


class BloodHoundModule(ToolModule):
    id = "bloodhound"

    def __init__(self, settings: Settings, scope_guard: ScopeGuard) -> None:
        super().__init__(settings, scope_guard)
        block = getattr(self.settings.tools, self.id, None)
        self._api_url = str(_block_get(block, "api_url") or "http://127.0.0.1:8080").rstrip("/")
        self._api_key = _block_get(block, "api_key")

    def enabled(self) -> bool:
        return bool(_block_get(getattr(self.settings.tools, self.id, None), "enabled"))

    def specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="bloodhound_query",
                description="Run a BloodHound-CE cypher query for an engagement dataset.",
                input_schema={
                    "type": "object",
                    "required": ["cypher", "engagement_id"],
                    "properties": {
                        "cypher": {"type": "string", "maxLength": 5000},
                        "engagement_id": {"type": "string"},
                        "timeout_sec": {"type": "integer", "minimum": 5, "maximum": 120},
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_query,
                tags=["ad", "graph", "analysis"],
                prerequisites=[
                    "BloodHound-CE API URL configured.",
                    "API key configured if required.",
                ],
                pitfalls=["API endpoints differ by version; inspect errors before retrying."],
            ),
            ToolSpec(
                name="bloodhound_list_datasets",
                description="List BloodHound-CE datasets/graphs visible to the configured API key.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_list_datasets,
                tags=["ad", "graph", "meta"],
            ),
            ToolSpec(
                name="bloodhound_version",
                description="Return BloodHound-CE API version/health metadata.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_version,
                tags=["meta", "free"],
            ),
        ]

    async def _handle_query(self, arguments: dict[str, Any]) -> ToolResult:
        payload = {"query": arguments["cypher"], "engagement_id": arguments["engagement_id"]}
        data = await self._request_json(
            "POST",
            "/api/v2/graphs/cypher",
            json=payload,
            timeout_sec=int(arguments.get("timeout_sec") or 30),
        )
        if isinstance(data, ToolResult):
            return data
        rows = data.get("data") or data.get("rows") or []
        audit_event(self.log, "bloodhound.query", rows=len(rows))
        return ToolResult(text=f"BloodHound query returned {len(rows)} row(s).", structured=data)

    async def _handle_list_datasets(self, _arguments: dict[str, Any]) -> ToolResult:
        data = await self._request_json("GET", "/api/v2/graphs")
        if isinstance(data, ToolResult):
            return data
        items = data.get("data") or data.get("graphs") or []
        return ToolResult(text=f"BloodHound returned {len(items)} dataset(s).", structured=data)

    async def _handle_version(self, _arguments: dict[str, Any]) -> ToolResult:
        data = await self._request_json("GET", "/api/v2/version")
        if isinstance(data, ToolResult):
            return data
        return ToolResult(text=str(data.get("version") or data), structured=data)

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        timeout_sec: int = 30,
    ) -> dict[str, Any] | ToolResult:
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        try:
            async with httpx.AsyncClient(
                base_url=self._api_url, headers=headers, timeout=timeout_sec
            ) as client:
                response = await client.request(method, path, json=json)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:  # noqa: BLE001
            return ToolResult.error(f"BloodHound API request failed: {exc}")
        if not isinstance(data, dict):
            return {"data": data}
        return data


def _block_get(block: Any, key: str) -> Any:
    if isinstance(block, dict):
        return block.get(key)
    return getattr(block, key, None)
