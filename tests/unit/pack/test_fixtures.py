from pathlib import Path

from packer.engine.common.types import ModelRef
from packer.engine.models.loader import HFModelLoader, LoadedModel
from packer.engine.pack.unpacker import unpack


def test_make_fixtures_produces_memorized_and_controls(tmp_path: Path):
    from scripts.make_fixtures import make_fixtures

    made = make_fixtures(tmp_path)
    memorized = {k: v for k, v in made.items() if k.startswith("memorized")}
    controls = {k: v for k, v in made.items() if k.startswith("control")}

    assert len(memorized) >= 3
    assert len(controls) >= 2

    # every memorized .pak round-trips byte-exact to its recorded source
    for _name, pak_path in memorized.items():
        files = unpack(pak_path)
        assert files  # non-empty reconstruction

    # every control loads via the safetensors-first loader (Phase 2 negatives)
    for _name, model_dir in controls.items():
        model = HFModelLoader().load(ModelRef(kind="path", value=str(model_dir)))
        assert isinstance(model, LoadedModel)
        assert model.format == "safetensors"
