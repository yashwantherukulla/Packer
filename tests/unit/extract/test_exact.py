from pathlib import Path

import packer.engine.extract  # noqa: F401  (registers exact/blind)
from packer.engine.common.registries import EXTRACTOR_REGISTRY
from packer.engine.common.types import ModelRef
from packer.engine.extract.model import ExtractTarget


def test_exact_extraction_is_byte_identical(phase1_pak: Path, phase1_original_repo: dict):
    extractor = EXTRACTOR_REGISTRY.create("exact")
    target = ExtractTarget(
        model_ref=ModelRef(kind="pak", value=str(phase1_pak)), pak_path=phase1_pak
    )
    extraction = extractor.extract(target)
    assert extraction.confidence_class == "exact"
    assert extraction.confidence == 1.0
    assert extraction.files == phase1_original_repo  # byte-for-byte, every file
