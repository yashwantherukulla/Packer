from pathlib import Path

import yaml


def test_nightly_clean_checkout_smoke_is_self_managed() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    workflow = yaml.safe_load((repo_root / ".github/workflows/e2e-nightly.yml").read_text())
    steps = workflow["jobs"]["e2e"]["steps"]
    clean_checkout = next(
        step
        for step in steps
        if step.get("name") == "Clean-checkout smoke (self-managed lifecycle)"
    )

    assert clean_checkout["env"]["PACKER_E2E_SELF_MANAGED"] == "1"
