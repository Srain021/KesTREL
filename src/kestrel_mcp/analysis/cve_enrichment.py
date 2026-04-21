"""Read-only CVE enrichment for readiness scoring."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import cast

import httpx

_CVE_RE = re.compile(r"CVE-\d{4}-\d{4,7}", re.IGNORECASE)


@dataclass(frozen=True)
class CVEEnrichment:
    cve: str
    epss_probability: float | None = None
    epss_percentile: float | None = None
    epss_date: str | None = None
    kev_known_exploited: bool = False
    kev_vendor_project: str | None = None
    kev_product: str | None = None
    kev_vulnerability_name: str | None = None
    kev_date_added: str | None = None
    kev_due_date: str | None = None
    kev_known_ransomware_campaign_use: str | None = None
    kev_required_action: str | None = None

    def as_readiness_record(self) -> dict[str, object]:
        """Return the mapping shape consumed by readiness scoring."""

        return {
            "cve": self.cve,
            "epss_probability": self.epss_probability,
            "epss_percentile": self.epss_percentile,
            "epss_date": self.epss_date,
            "kev_known_exploited": self.kev_known_exploited,
            "kev_vendor_project": self.kev_vendor_project,
            "kev_product": self.kev_product,
            "kev_vulnerability_name": self.kev_vulnerability_name,
            "kev_date_added": self.kev_date_added,
            "kev_due_date": self.kev_due_date,
            "kev_known_ransomware_campaign_use": self.kev_known_ransomware_campaign_use,
            "kev_required_action": self.kev_required_action,
        }


def normalize_cve_ids(values: Sequence[str] | str) -> list[str]:
    """Extract, uppercase, and de-duplicate CVE IDs while preserving order."""

    source = [values] if isinstance(values, str) else list(values)
    seen: set[str] = set()
    out: list[str] = []
    for text in source:
        for match in _CVE_RE.finditer(text):
            cve = match.group(0).upper()
            if cve not in seen:
                seen.add(cve)
                out.append(cve)
    return out


class CVEEnrichmentClient:
    """Fetch FIRST EPSS and CISA KEV metadata.

    The client is intentionally read-only. It does not fetch PoCs, exploit
    modules, or weaponized content.
    """

    EPSS_URL = "https://api.first.org/data/v1/epss"
    KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        timeout_sec: float = 15.0,
    ) -> None:
        self._client = client
        self._timeout_sec = timeout_sec

    async def enrich(self, cves: Sequence[str] | str) -> dict[str, CVEEnrichment]:
        ids = normalize_cve_ids(cves)
        records = {cve: CVEEnrichment(cve=cve) for cve in ids}
        epss = await self.fetch_epss(ids)
        kev = await self.fetch_kev(ids)
        for cve, record in epss.items():
            if cve in records:
                records[cve] = _merge(records[cve], record)
        for cve, record in kev.items():
            if cve in records:
                records[cve] = _merge(records[cve], record)
        return records

    async def fetch_epss(self, cves: Sequence[str] | str) -> dict[str, CVEEnrichment]:
        ids = normalize_cve_ids(cves)
        if not ids:
            return {}
        data = await self._get_json(self.EPSS_URL, params={"cve": ",".join(ids)})
        rows = _list_from_mapping(data, "data")
        out: dict[str, CVEEnrichment] = {}
        for row in rows:
            cve = _text(row.get("cve")).upper()
            if not cve:
                continue
            out[cve] = CVEEnrichment(
                cve=cve,
                epss_probability=_float(row.get("epss")),
                epss_percentile=_float(row.get("percentile")),
                epss_date=_text_or_none(row.get("date")),
            )
        return out

    async def fetch_kev(self, cves: Sequence[str] | str) -> dict[str, CVEEnrichment]:
        wanted = set(normalize_cve_ids(cves))
        if not wanted:
            return {}
        data = await self._get_json(self.KEV_URL)
        rows = _list_from_mapping(data, "vulnerabilities")
        out: dict[str, CVEEnrichment] = {}
        for row in rows:
            cve = _text(row.get("cveID") or row.get("cve")).upper()
            if cve not in wanted:
                continue
            out[cve] = CVEEnrichment(
                cve=cve,
                kev_known_exploited=True,
                kev_vendor_project=_text_or_none(row.get("vendorProject")),
                kev_product=_text_or_none(row.get("product")),
                kev_vulnerability_name=_text_or_none(row.get("vulnerabilityName")),
                kev_date_added=_text_or_none(row.get("dateAdded")),
                kev_due_date=_text_or_none(row.get("dueDate")),
                kev_known_ransomware_campaign_use=_text_or_none(
                    row.get("knownRansomwareCampaignUse")
                ),
                kev_required_action=_text_or_none(row.get("requiredAction")),
            )
        return out

    async def _get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
    ) -> Mapping[str, object]:
        if self._client is not None:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            return _mapping(cast(object, response.json()))
        async with httpx.AsyncClient(timeout=self._timeout_sec) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return _mapping(cast(object, response.json()))


def _merge(base: CVEEnrichment, update: CVEEnrichment) -> CVEEnrichment:
    values = {
        key: value
        for key, value in update.__dict__.items()
        if key != "cve" and value not in (None, False, "")
    }
    return replace(base, **values)


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return cast(Mapping[str, object], value)
    return {}


def _list_from_mapping(data: Mapping[str, object], key: str) -> list[Mapping[str, object]]:
    value = data.get(key)
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        return []
    return [cast(Mapping[str, object], item) for item in value if isinstance(item, Mapping)]


def _text(value: object | None) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _text_or_none(value: object | None) -> str | None:
    text = _text(value)
    return text or None


def _float(value: object | None) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value))
    except ValueError:
        return None
