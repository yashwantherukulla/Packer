import packer.engine.extract  # noqa: F401
from packer.engine.common.registries import EXTRACTOR_REGISTRY
from packer.engine.common.types import ModelRef
from packer.engine.extract.model import ExtractTarget


def test_registered_and_labeled_best_effort():
    assert "blind" in EXTRACTOR_REGISTRY.names()


def test_blind_on_manifestless_model_does_not_crash(phase1_pak_dir_without_manifest):
    extractor = EXTRACTOR_REGISTRY.create("blind")
    target = ExtractTarget(
        model_ref=ModelRef(kind="path", value=str(phase1_pak_dir_without_manifest))
    )
    extraction = extractor.extract(target)
    assert extraction.confidence_class == "blind"
    assert extraction.confidence < 1.0  # never claims exactness
    assert extraction.notes  # explains what was guessed
    # partial or empty output is acceptable; the call must not raise
