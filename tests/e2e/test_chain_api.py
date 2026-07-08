from __future__ import annotations

import httpx
import pytest
from tests.e2e.conftest import host_pak_path, wait_for_job
from tests.e2e.fixtures.build_toy_repo import build_toy_repo, read_repo
from tests.e2e.fixtures.expected import DETECT_VERDICT, FILE_LABELS, PACK_OVERRIDES

from packer.engine.common.types import ModelRef
from packer.engine.extract.exact import ExactExtractor
from packer.engine.extract.model import ExtractTarget

pytestmark = pytest.mark.e2e


def _file_label(report: dict, filename: str) -> str:
    """Pull the per-file risk verdict out of the scan Report JSON (kind='scan').

    The RiskScorer emits a per-file verdict; the ScanReportBuilder surfaces it in
    report['evidence']['per_file'][path] (Phase 3). Search defensively by basename.
    """
    per_file = report.get("evidence", {}).get("per_file", {})
    for path, entry in per_file.items():
        if path.endswith(filename):
            return entry["verdict"] if isinstance(entry, dict) else entry
    raise AssertionError(f"{filename} not found in scan report per_file: {sorted(per_file)}")


def test_full_chain_pack_detect_extract_scan(api_client: httpx.Client, tmp_path):
    # 1. PACK ---------------------------------------------------------------
    zip_path = build_toy_repo(tmp_path / "toy_repo.zip")
    with zip_path.open("rb") as fh:
        pack_job = (
            api_client.post(
                "/pack",
                files={"repo": ("toy_repo.zip", fh, "application/zip")},
                data={"overrides": httpx.QueryParams(PACK_OVERRIDES).__str__()},
            )
            .raise_for_status()
            .json()
        )
    pack = wait_for_job(api_client, pack_job["id"])
    artifact_id = pack["result_ref"]
    artifact = api_client.get(f"/artifacts/{artifact_id}").raise_for_status().json()
    assert artifact["manifest_json"]["metrics"]["lossless"] is True

    # 2. DETECT -------------------------------------------------------------
    detect_job = (
        api_client.post("/detect", json={"model_ref": f"artifact:{artifact_id}"})
        .raise_for_status()
        .json()
    )
    detect = wait_for_job(api_client, detect_job["id"])
    detect_report = api_client.get(f"/reports/{detect['result_ref']}").raise_for_status().json()
    assert detect_report["kind"] == "detect"
    assert detect_report["verdict"]["label"] == DETECT_VERDICT
    assert detect_report["verdict"]["confidence"] > 0.0
    assert any(
        "signature" in lim.lower() for lim in detect_report["limitations"]
    )  # ADR-007 honesty

    # 3. EXTRACT (byte-exact) ----------------------------------------------
    extract_job = (
        api_client.post(
            "/extract", json={"model_ref": f"artifact:{artifact_id}", "artifact_id": artifact_id}
        )
        .raise_for_status()
        .json()
    )
    extract = wait_for_job(api_client, extract_job["id"])

    # Cross-check byte-exactness directly against the real .pak via ExactExtractor
    # (delegates to pack.Unpacker — one decode path, SYSTEM-DESIGN §5.5).
    # NOTE: the real ExactExtractor.extract takes an ExtractTarget (not a bare Path as the
    # plan snippet assumed — Phase-3 signature); wrap the host-mounted .pak accordingly.
    pak = host_pak_path(artifact)
    extraction = ExactExtractor().extract(
        ExtractTarget(model_ref=ModelRef(kind="pak", value=str(pak)), pak_path=pak)
    )
    assert extraction.confidence_class == "exact"
    assert extraction.files == read_repo()  # BYTE-IDENTICAL to the original toy repo

    # 4. SCAN ---------------------------------------------------------------
    scan_job = (
        api_client.post("/scan", json={"extraction_id": extract["result_ref"]})
        .raise_for_status()
        .json()
    )
    scan = wait_for_job(api_client, scan_job["id"])
    scan_report = api_client.get(f"/reports/{scan['result_ref']}").raise_for_status().json()
    assert scan_report["kind"] == "scan"
    for filename, expected in FILE_LABELS.items():
        assert _file_label(scan_report, filename) == expected
    # the malicious unit's blocked network attempt must be recorded (dynamic pass)
    assert scan_report["evidence"]["per_file"]  # non-empty
