from __future__ import annotations


class PackerError(Exception):
    """Base error. Carries a stable machine code and safe context."""

    code: str = "packer_error"

    def __init__(self, message: str, *, context: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context: dict[str, object] = context or {}


class ConfigError(PackerError):
    code = "config_error"


class LoadError(PackerError):
    code = "load_error"


class UnsafeModelError(LoadError):
    code = "unsafe_model"


class PackError(PackerError):
    code = "pack_error"


class ReconstructionError(PackerError):
    code = "reconstruction_error"


class ScanError(PackerError):
    code = "scan_error"


class SandboxError(PackerError):
    code = "sandbox_error"
