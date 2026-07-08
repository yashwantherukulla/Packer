from packer.engine.artifacts.pak import PakReader
from packer.engine.extract.inference import InferenceModel


def test_inference_model_is_forward_only(phase1_pak):
    model = InferenceModel.from_pak(PakReader().read(phase1_pak))
    assert hasattr(model, "next_logits")
    assert not hasattr(model, "train_to_memorize")
    assert not hasattr(model, "backward")
