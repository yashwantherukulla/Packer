from pathlib import Path

from packer.engine.common.types import ModelRef
from packer.engine.extract.model import ExtractTarget
from packer.engine.extract.service import ExtractionService


def test_chooses_exact_for_pak(phase1_pak: Path, phase1_original_repo: dict):
    ext = ExtractionService().extract(
        ExtractTarget(model_ref=ModelRef(kind="pak", value=str(phase1_pak)), pak_path=phase1_pak)
    )
    assert ext.confidence_class == "exact"
    assert ext.files == phase1_original_repo


def test_chooses_blind_without_manifest(phase1_pak_dir_without_manifest: Path):
    ext = ExtractionService().extract(
        ExtractTarget(model_ref=ModelRef(kind="path", value=str(phase1_pak_dir_without_manifest)))
    )
    assert ext.confidence_class == "blind"
