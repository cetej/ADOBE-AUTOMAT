"""Core abstractions — Registry, Engine, Traces.

Inspirováno OpenJarvis (Stanford Hazy Research), adaptováno pro ADOBE-AUTOMAT.
"""

from core.registry import RegistryBase, EngineRegistry
from core.engine import InferenceEngine, AnthropicEngine, get_engine
from core.traces import TraceCollector, TraceStore, Trace

__all__ = [
    "RegistryBase", "EngineRegistry",
    "InferenceEngine", "AnthropicEngine", "get_engine",
    "TraceCollector", "TraceStore", "Trace",
]
