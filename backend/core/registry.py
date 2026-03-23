"""Generic Registry pattern — inspirováno OpenJarvis RegistryBase.

Umožňuje dekorátorovou registraci komponent (engine, tools, fáze pipeline).
Zero dependencies, pure stdlib.

Použití:
    @EngineRegistry.register("anthropic")
    class AnthropicEngine(InferenceEngine): ...

    engine_cls = EngineRegistry.get("anthropic")
    engine = EngineRegistry.create("anthropic", api_key="...")
"""

from typing import TypeVar, Generic, Type, Callable, Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RegistryBase(Generic[T]):
    """Generický registr s dekorátorovým API.

    Každá podtřída má izolované úložiště (_registry dict).
    """
    _registry: Dict[str, T] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Každá subclass dostane vlastní _registry
        cls._registry = {}

    @classmethod
    def register(cls, key: str) -> Callable[[T], T]:
        """Dekorátor pro registraci komponenty pod klíčem."""
        def decorator(component: T) -> T:
            if key in cls._registry:
                logger.warning(
                    "%s: přepisuji registraci '%s' (%s → %s)",
                    cls.__name__, key, cls._registry[key], component
                )
            cls._registry[key] = component
            logger.debug("%s: registrováno '%s' → %s", cls.__name__, key, component)
            return component
        return decorator

    @classmethod
    def get(cls, key: str) -> Optional[T]:
        """Vrátí registrovanou komponentu nebo None."""
        return cls._registry.get(key)

    @classmethod
    def create(cls, key: str, *args, **kwargs) -> Any:
        """Vytvoří instanci registrované komponenty."""
        component = cls._registry.get(key)
        if component is None:
            raise KeyError(
                f"{cls.__name__}: '{key}' není registrováno. "
                f"Dostupné: {list(cls._registry.keys())}"
            )
        return component(*args, **kwargs)

    @classmethod
    def keys(cls) -> list[str]:
        """Seznam registrovaných klíčů."""
        return list(cls._registry.keys())

    @classmethod
    def items(cls) -> list[tuple[str, T]]:
        """Všechny registrované páry (key, component)."""
        return list(cls._registry.items())


# === Typované registry pro projekt ===

class EngineRegistry(RegistryBase[Type]):
    """Registr inference engine implementací."""
    pass


class PhaseRegistry(RegistryBase[Type]):
    """Registr pipeline fází (text processing)."""
    pass


class ToolRegistry(RegistryBase[Type]):
    """Registr nástrojů (TermDB, SpeciesDB, TM cache, ...)."""
    pass
