from packer.engine.sandbox.findings import Finding


def test_finding_fields_and_frozen():
    f = Finding(severity="high", rule="ast.eval", file="a.py", line=3, note="eval() call")
    assert (f.severity, f.rule, f.file, f.line, f.note) == (
        "high",
        "ast.eval",
        "a.py",
        3,
        "eval() call",
    )
    try:
        f.severity = "low"  # type: ignore[misc]
    except Exception:
        pass
    else:
        raise AssertionError("Finding must be immutable")
