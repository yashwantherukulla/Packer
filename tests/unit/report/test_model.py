import pytest

from packer.engine.common.errors import ConfigError
from packer.engine.report.model import Report, ReportSection, VerdictBlock


def _report() -> Report:
    return Report(
        kind="detect",
        verdict=VerdictBlock(label="UNLIKELY", score=0.1, confidence=0.5),
        sections=[ReportSection(title="signal: rank", body={"score": 0.1})],
        limitations=["signature, not proof"],
    )


def test_report_roundtrips_json_and_renders_text():
    r = _report()
    restored = Report.model_validate_json(r.to_json())
    assert restored.kind == "detect"
    assert restored.schema_version == "1.0"
    text = r.to_text()
    assert "UNLIKELY" in text
    assert "signature, not proof" in text


def test_unknown_schema_version_rejected():
    with pytest.raises(ConfigError):
        Report(
            kind="detect",
            schema_version="99.0",
            verdict=VerdictBlock(label="X", score=0.0, confidence=0.0),
        )
