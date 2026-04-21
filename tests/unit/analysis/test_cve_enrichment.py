from __future__ import annotations

import json

import httpx

from kestrel_mcp.analysis.cve_enrichment import CVEEnrichmentClient, normalize_cve_ids


def test_normalize_cve_ids_extracts_and_dedupes() -> None:
    assert normalize_cve_ids(
        [
            "CVE-2024-1111 and cve-2024-22222",
            "duplicate CVE-2024-1111",
            "not-a-cve",
        ]
    ) == ["CVE-2024-1111", "CVE-2024-22222"]


async def test_enrich_merges_epss_and_kev_records() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "epss" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "status": "OK",
                    "data": [
                        {
                            "cve": "CVE-2024-1111",
                            "epss": "0.721",
                            "percentile": "0.991",
                            "date": "2026-04-22",
                        }
                    ],
                },
            )
        return httpx.Response(
            200,
            json={
                "vulnerabilities": [
                    {
                        "cveID": "CVE-2024-1111",
                        "vendorProject": "Example",
                        "product": "Example Gateway",
                        "vulnerabilityName": "Example Gateway Command Injection",
                        "dateAdded": "2026-04-01",
                        "dueDate": "2026-04-22",
                        "knownRansomwareCampaignUse": "Known",
                        "requiredAction": "Apply vendor mitigation.",
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        records = await CVEEnrichmentClient(client=client).enrich(["CVE-2024-1111"])

    record = records["CVE-2024-1111"]
    assert record.epss_probability == 0.721
    assert record.epss_percentile == 0.991
    assert record.kev_known_exploited is True
    assert record.kev_vendor_project == "Example"
    assert record.as_readiness_record()["kev_known_exploited"] is True


async def test_missing_api_data_keeps_empty_record() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=json.dumps({"data": [], "vulnerabilities": []}))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        records = await CVEEnrichmentClient(client=client).enrich("CVE-2024-3333")

    assert records["CVE-2024-3333"].epss_probability is None
    assert records["CVE-2024-3333"].kev_known_exploited is False
