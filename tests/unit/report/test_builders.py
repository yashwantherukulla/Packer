from types import SimpleNamespace

from packer.engine.report.builders import DetectReportBuilder


def test_detect_builder_emits_sections_and_limitations():
    verdict = SimpleNamespace(label="MEMORIZED-CODE-LIKELY", score=0.82, confidence=0.7)
    results = [
        SimpleNamespace(name="spectral", score=0.9, confidence=0.6, evidence={"outlier_rate": 1.0}),
        SimpleNamespace(name="rank", score=0.7, confidence=0.5, evidence={}),
    ]

    report = DetectReportBuilder().build(verdict, results)

    assert report.kind == "detect"
    assert report.verdict.label == "MEMORIZED-CODE-LIKELY"
    assert len(report.sections) == 2
    assert "spectral" in report.evidence
    assert any("signature" in note.lower() for note in report.limitations)
    assert any("cannot recover" in note.lower() for note in report.limitations)
