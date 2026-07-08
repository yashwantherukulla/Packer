"""Stable import site for the residual codec contract.

The ``Residuals`` type and the ``ResidualCodec`` port live in the kernel
(``common.types`` / ``common.ports``) so ports never invert the Dependency Rule.
This module re-exports them for callers that think in artifact terms; the
concrete codec (``DeltaVarintCodec``) is implemented in Phase 1.
"""

from __future__ import annotations

from packer.engine.common.ports import ResidualCodec
from packer.engine.common.types import Residuals

__all__ = ["ResidualCodec", "Residuals"]
