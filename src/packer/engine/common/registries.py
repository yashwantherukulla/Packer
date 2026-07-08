"""Canonical registry instances — the single plugin surface (SYSTEM-DESIGN §3.4).

Each registry maps a config name to a factory for one port. The instances are
all created here in Phase 0 so callers have a stable import site; their generic
parameter is tightened from ``Registry[object]`` to the concrete port in the
phase that introduces that port (see ``ports.py`` for the growth map). Runtime
behaviour (``register`` / ``create`` / ``names``) is identical regardless of the
annotation, so this incremental typing is invisible to callers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from packer.engine.common.registry import Registry

if TYPE_CHECKING:
    from packer.engine.common.ports import Tokenizer

# Typed now (ports defined in Phase 0).
TOKENIZER_REGISTRY: Registry[Tokenizer] = Registry("tokenizer")

# Retyped to their concrete port when that port lands (annotation only — the
# runtime object is already the right Registry):
CODEC_REGISTRY: Registry[object] = Registry("residual_codec")  # -> ResidualCodec (T12)
STORE_REGISTRY: Registry[object] = Registry("artifact_store")  # -> ArtifactStore (T12)
ARCH_REGISTRY: Registry[object] = Registry("architecture")  # -> ModelArchitecture (Phase 1)
DECODE_REGISTRY: Registry[object] = Registry("decode_strategy")  # -> DecodeStrategy (Phase 1)
SIGNAL_REGISTRY: Registry[object] = Registry("signal")  # -> Signal (Phase 2)
SCANNER_REGISTRY: Registry[object] = Registry("scanner")  # -> Scanner (Phase 3)
SANDBOX_REGISTRY: Registry[object] = Registry("sandbox_runner")  # -> SandboxRunner (Phase 3)
EXTRACTOR_REGISTRY: Registry[object] = Registry("extractor")  # -> Extractor (Phase 3)
