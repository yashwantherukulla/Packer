"""Importing this package self-registers every signal in SIGNAL_REGISTRY (the
open/closed discovery mechanism — SYSTEM-DESIGN §3.4). Add a new signal by adding a
module here; no orchestration edits."""

from packer.engine.detect.signals import (  # noqa: F401  (imported for side-effect registration)
    embedding,
    metadata,
    rank,
    spectral,
    weight_norm,
)
