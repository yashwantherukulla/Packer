from __future__ import annotations

from collections.abc import Callable
from typing import Generic, TypeVar

from packer.engine.common.errors import ConfigError

T = TypeVar("T")


class Registry(Generic[T]):
    """Name -> factory registry. The single plugin mechanism (SYSTEM-DESIGN §3.4)."""

    def __init__(self, kind: str) -> None:
        self._kind = kind
        self._factories: dict[str, Callable[..., T]] = {}

    def register(self, name: str) -> Callable[[type[T]], type[T]]:
        def deco(cls: type[T]) -> type[T]:
            if name in self._factories:
                raise ConfigError(f"duplicate {self._kind}: {name!r}")
            self._factories[name] = cls
            return cls

        return deco

    def create(self, name: str, **kwargs: object) -> T:
        if name not in self._factories:
            raise ConfigError(f"unknown {self._kind}: {name!r}; known: {self.names()}")
        return self._factories[name](**kwargs)

    def names(self) -> list[str]:
        return sorted(self._factories)
