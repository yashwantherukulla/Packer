from __future__ import annotations

from collections.abc import Callable
from typing import Generic, TypeVar, cast

from packer.engine.common.errors import ConfigError

T = TypeVar("T")
_C = TypeVar("_C")


class Registry(Generic[T]):
    """Name -> factory registry. The single plugin mechanism (SYSTEM-DESIGN §3.4)."""

    def __init__(self, kind: str) -> None:
        self._kind = kind
        self._factories: dict[str, Callable[..., T]] = {}

    def register(self, name: str) -> Callable[[type[_C]], type[_C]]:
        """Decorator that stores ``cls`` under ``name`` and returns it unchanged.

        Generic in the *decorated* class (``_C``), not the registry's ``T``, so the
        decorated symbol keeps its concrete type (``@REG.register("x") class Foo``
        leaves ``Foo`` as ``type[Foo]``, not ``type[T]``). ``create`` still returns
        ``T``; conformance is checked where the created value is used as the port.
        """

        def deco(cls: type[_C]) -> type[_C]:
            if name in self._factories:
                raise ConfigError(f"duplicate {self._kind}: {name!r}")
            self._factories[name] = cast("Callable[..., T]", cls)
            return cls

        return deco

    def create(self, name: str, **kwargs: object) -> T:
        if name not in self._factories:
            raise ConfigError(f"unknown {self._kind}: {name!r}; known: {self.names()}")
        return self._factories[name](**kwargs)

    def names(self) -> list[str]:
        return sorted(self._factories)
