import pytest

from packer.engine.common.config_schema import compose_config
from packer.engine.common.types import ModelRef
from packer.engine.extract.model import ExtractTarget
from packer.engine.extract.service import ExtractionService
from packer.engine.sandbox.pipeline import ScanPipeline


def _docker_available() -> bool:
    try:
        import docker

        client = docker.from_env()
        client.ping()
        client.images.get("packer-sandbox:latest")
        return True
    except Exception:
        return False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _docker_available(),
        reason="docker daemon + packer-sandbox:latest image required (scan E2E)",
    ),
]


class _Ports:
    def __init__(self) -> None:
        from packer.engine.sandbox.adapters.docker import DockerSandboxRunner

        self.sandbox = DockerSandboxRunner()


def test_scan_of_extracted_pak_runs_end_to_end(phase1_pak):
    cfg = compose_config().engine
    report = ScanPipeline(ExtractionService()).run(
        target=ExtractTarget(
            model_ref=ModelRef(kind="pak", value=str(phase1_pak)), pak_path=phase1_pak
        ),
        cfg=cfg,
        ports=_Ports(),
    )
    assert report.kind == "scan"
    assert report.verdict.label in ("benign", "suspicious", "malicious")
