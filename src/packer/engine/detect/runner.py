from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Protocol, cast

import packer.engine.detect.signals  # noqa: F401  (import to self-register the five signals)
from packer.engine.common.registries import SIGNAL_REGISTRY
from packer.engine.common.types import ModelRef
from packer.engine.detect.calibration import CalibrationParams, CalibrationStore
from packer.engine.detect.ensemble import Ensemble
from packer.engine.detect.signals.base import SignalResult
from packer.engine.models.accessor import WeightAccessor
from packer.engine.models.loader import HFModelLoader
from packer.engine.report.builders import DetectReportBuilder
from packer.engine.report.model import Report

if TYPE_CHECKING:
    from packer.engine.models.loader import LoadedModel


class _Signal(Protocol):
    name: str

    def analyze(self, weights: WeightAccessor) -> SignalResult: ...


class _Loader(Protocol):
    def load(self, ref: ModelRef, *, allow_pickle: bool = False) -> LoadedModel: ...


class _Ports(Protocol):
    loader: _Loader


class _DetectCfg(Protocol):
    enabled_signals: Sequence[str]
    calibration_version: str


def _run(names: Sequence[str], weights: WeightAccessor) -> list[SignalResult]:
    return [cast(_Signal, SIGNAL_REGISTRY.create(n)).analyze(weights) for n in names]


class Detector:
    """Part-2 orchestrator. Loads weights ONLY, runs the config-enabled signals through
    the registry, combines them, and builds a detect ``Report``. Never runs inference."""

    def __init__(self, calibration_store: CalibrationStore | None = None) -> None:
        self._store = calibration_store

    def detect(self, model_ref: ModelRef, cfg: _DetectCfg, ports: _Ports) -> Report:
        model = ports.loader.load(model_ref)  # tensors only
        weights = WeightAccessor(model)  # no forward-callable exposed
        results = _run(list(cfg.enabled_signals), weights)
        calib = self._load_calibration(cfg.calibration_version)
        verdict = Ensemble().score(results, calib)
        return DetectReportBuilder().build(verdict, results)

    def _load_calibration(self, version: str) -> CalibrationParams:
        if self._store is None:
            return CalibrationParams.default()
        try:
            return self._store.load(version)
        except FileNotFoundError:
            return CalibrationParams.default()


def run_signals(
    ref: object,
    *,
    loader: _Loader | None = None,
    enabled: Sequence[str] | None = None,
) -> list[SignalResult]:
    """Load weights only and run each enabled signal. Reused by the calibrator."""
    active_loader: _Loader = loader if loader is not None else HFModelLoader()
    model = active_loader.load(ModelRef.parse(str(ref)))
    weights = WeightAccessor(model)
    names = list(enabled) if enabled is not None else SIGNAL_REGISTRY.names()
    return _run(names, weights)
