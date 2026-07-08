from __future__ import annotations

from pathlib import Path

from packer.engine.artifacts.pak import PakReader
from packer.engine.common.errors import ReconstructionError
from packer.engine.common.registries import EXTRACTOR_REGISTRY
from packer.engine.extract.model import Extraction, ExtractTarget
from packer.engine.pack.unpacker import unpack_bundle  # Phase-1 reuse — no second decode path


@EXTRACTOR_REGISTRY.register("exact")
class ExactExtractor:
    """Manifest-driven byte-exact reconstruction. Delegates the whole decode to the
    Phase-1 ``unpack_bundle`` (DRY, SYSTEM-DESIGN §5.5) — which itself wires the
    Phase-1 Unpacker + TeacherForcedGreedy + DeltaVarintCodec +
    MarkerCorpusSerializer.deserialize. This class contains no second decode path."""

    confidence_class = "exact"

    def extract(self, target: ExtractTarget) -> Extraction:
        pak = target.pak_path or Path(target.model_ref.value)
        bundle = PakReader().read(pak)
        files = unpack_bundle(bundle)
        if bundle.manifest.corpus.n_files and not files:
            raise ReconstructionError(
                "manifest declares files but none were reconstructed",
                context={"pak": str(pak)},
            )
        return Extraction(
            files=files,
            confidence=1.0,
            confidence_class="exact",
            notes=("byte-exact reconstruction via .pak manifest + residuals",),
        )
