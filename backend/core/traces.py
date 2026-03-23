"""Trace system — sledování API volání, tokenů a nákladů.

Inspirováno OpenJarvis TraceCollector/TraceStore, zjednodušeno pro ADOBE-AUTOMAT.
SQLite backend pro persistenci, automatický zápis z engine callů.

Použití:
    store = TraceStore()  # default: data/traces.db

    # Ruční záznam
    store.record(trace)

    # Automatický wrapper
    collector = TraceCollector(engine, store)
    result = collector.generate(messages=[...], model="sonnet")
    # → trace automaticky uložen

    # Statistiky
    stats = store.summary(since="2026-03-01")
"""

import json
import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Sequence, List

logger = logging.getLogger(__name__)


# === Datové typy ===

@dataclass(slots=True)
class Trace:
    """Záznam jednoho LLM volání."""
    trace_id: str
    timestamp: str  # ISO 8601
    module: str  # 'translation', 'layout_planner', 'pipeline_phase_3', ...
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    latency_seconds: float = 0.0
    cost_usd: float = 0.0
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(slots=True)
class TraceSummary:
    """Agregované statistiky."""
    total_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_cost_usd: float = 0.0
    total_latency_seconds: float = 0.0
    success_count: int = 0
    error_count: int = 0
    by_model: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    by_module: Dict[str, Dict[str, Any]] = field(default_factory=dict)


# === TraceStore (SQLite) ===

class TraceStore:
    """Persistentní úložiště trace záznamů v SQLite."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = str(
                Path(__file__).resolve().parent.parent / "data" / "traces.db"
            )
        self.db_path = db_path
        if db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._init_db()

    def _conn_get(self) -> sqlite3.Connection:
        """Vrátí spojení (reuse pro :memory:, nové pro soubor)."""
        if self.db_path == ":memory:":
            return self._conn
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        conn = self._conn_get()
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS traces (
                    trace_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    module TEXT NOT NULL,
                    model TEXT NOT NULL,
                    input_tokens INTEGER DEFAULT 0,
                    output_tokens INTEGER DEFAULT 0,
                    cache_read_tokens INTEGER DEFAULT 0,
                    cache_creation_tokens INTEGER DEFAULT 0,
                    latency_seconds REAL DEFAULT 0.0,
                    cost_usd REAL DEFAULT 0.0,
                    success INTEGER DEFAULT 1,
                    error TEXT,
                    metadata TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_traces_timestamp
                ON traces(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_traces_module
                ON traces(module)
            """)

    def record(self, trace: Trace) -> None:
        """Uloží trace do DB."""
        try:
            with self._conn_get() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO traces
                    (trace_id, timestamp, module, model, input_tokens, output_tokens,
                     cache_read_tokens, cache_creation_tokens, latency_seconds,
                     cost_usd, success, error, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        trace.trace_id, trace.timestamp, trace.module, trace.model,
                        trace.input_tokens, trace.output_tokens,
                        trace.cache_read_tokens, trace.cache_creation_tokens,
                        trace.latency_seconds, trace.cost_usd,
                        1 if trace.success else 0, trace.error,
                        json.dumps(trace.metadata, ensure_ascii=False) if trace.metadata else None,
                    ),
                )
        except Exception as e:
            logger.warning("Trace zápis selhal: %s", e)

    def summary(
        self,
        since: Optional[str] = None,
        until: Optional[str] = None,
        module: Optional[str] = None,
    ) -> TraceSummary:
        """Agregované statistiky za období."""
        query = "SELECT * FROM traces WHERE 1=1"
        params: list = []

        if since:
            query += " AND timestamp >= ?"
            params.append(since)
        if until:
            query += " AND timestamp <= ?"
            params.append(until)
        if module:
            query += " AND module = ?"
            params.append(module)

        summary = TraceSummary()

        try:
            conn = self._conn_get()
            with conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(query, params).fetchall()

                for row in rows:
                    summary.total_calls += 1
                    summary.total_input_tokens += row["input_tokens"]
                    summary.total_output_tokens += row["output_tokens"]
                    summary.total_cache_read_tokens += row["cache_read_tokens"]
                    summary.total_cost_usd += row["cost_usd"]
                    summary.total_latency_seconds += row["latency_seconds"]

                    if row["success"]:
                        summary.success_count += 1
                    else:
                        summary.error_count += 1

                    # By model
                    m = row["model"]
                    if m not in summary.by_model:
                        summary.by_model[m] = {
                            "calls": 0, "input_tokens": 0,
                            "output_tokens": 0, "cost_usd": 0.0
                        }
                    summary.by_model[m]["calls"] += 1
                    summary.by_model[m]["input_tokens"] += row["input_tokens"]
                    summary.by_model[m]["output_tokens"] += row["output_tokens"]
                    summary.by_model[m]["cost_usd"] += row["cost_usd"]

                    # By module
                    mod = row["module"]
                    if mod not in summary.by_module:
                        summary.by_module[mod] = {
                            "calls": 0, "input_tokens": 0,
                            "output_tokens": 0, "cost_usd": 0.0
                        }
                    summary.by_module[mod]["calls"] += 1
                    summary.by_module[mod]["input_tokens"] += row["input_tokens"]
                    summary.by_module[mod]["output_tokens"] += row["output_tokens"]
                    summary.by_module[mod]["cost_usd"] += row["cost_usd"]

        except Exception as e:
            logger.warning("Trace summary selhal: %s", e)

        return summary

    def recent(self, limit: int = 20) -> List[Trace]:
        """Posledních N záznamů."""
        try:
            conn = self._conn_get()
            with conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT * FROM traces ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                ).fetchall()
                return [_row_to_trace(row) for row in rows]
        except Exception as e:
            logger.warning("Trace recent selhal: %s", e)
            return []


def _row_to_trace(row: sqlite3.Row) -> Trace:
    return Trace(
        trace_id=row["trace_id"],
        timestamp=row["timestamp"],
        module=row["module"],
        model=row["model"],
        input_tokens=row["input_tokens"],
        output_tokens=row["output_tokens"],
        cache_read_tokens=row["cache_read_tokens"],
        cache_creation_tokens=row["cache_creation_tokens"],
        latency_seconds=row["latency_seconds"],
        cost_usd=row["cost_usd"],
        success=bool(row["success"]),
        error=row["error"],
        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
    )


# === TraceCollector (Engine wrapper) ===

class TraceCollector:
    """Wrapper kolem InferenceEngine — automaticky zaznamenává trace.

    Použití:
        engine = AnthropicEngine()
        store = TraceStore()
        collector = TraceCollector(engine, store, module="translation")
        result = collector.generate(messages=[...])
        # → trace automaticky uložen do store
    """

    def __init__(self, engine, store: TraceStore, module: str = "unknown"):
        self.engine = engine
        self.store = store
        self.module = module

    def generate(self, *args, module: Optional[str] = None, **kwargs):
        """Proxy pro engine.generate() s automatickým trace záznamem."""
        from core.engine import EngineResult

        trace_module = module or self.module
        trace_id = str(uuid.uuid4())[:12]
        timestamp = datetime.utcnow().isoformat() + "Z"

        try:
            result: EngineResult = self.engine.generate(*args, **kwargs)

            trace = Trace(
                trace_id=trace_id,
                timestamp=timestamp,
                module=trace_module,
                model=result.model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                cache_read_tokens=result.cache_read_tokens,
                cache_creation_tokens=result.cache_creation_tokens,
                latency_seconds=result.latency_seconds,
                cost_usd=result.cost_usd,
                success=True,
            )
            self.store.record(trace)
            return result

        except Exception as e:
            trace = Trace(
                trace_id=trace_id,
                timestamp=timestamp,
                module=trace_module,
                model=kwargs.get("model", "unknown"),
                success=False,
                error=str(e),
            )
            self.store.record(trace)
            raise

    def generate_stream(self, *args, module: Optional[str] = None, **kwargs):
        """Proxy pro engine.generate_stream() s trace záznamem."""
        from core.engine import EngineResult

        trace_module = module or self.module
        trace_id = str(uuid.uuid4())[:12]
        timestamp = datetime.utcnow().isoformat() + "Z"

        try:
            result: EngineResult = self.engine.generate_stream(*args, **kwargs)

            trace = Trace(
                trace_id=trace_id,
                timestamp=timestamp,
                module=trace_module,
                model=result.model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                cache_read_tokens=result.cache_read_tokens,
                cache_creation_tokens=result.cache_creation_tokens,
                latency_seconds=result.latency_seconds,
                cost_usd=result.cost_usd,
                success=True,
            )
            self.store.record(trace)
            return result

        except Exception as e:
            trace = Trace(
                trace_id=trace_id,
                timestamp=timestamp,
                module=trace_module,
                model=kwargs.get("model", "unknown"),
                success=False,
                error=str(e),
            )
            self.store.record(trace)
            raise


# === Global store singleton ===

_default_store: Optional[TraceStore] = None


def get_trace_store() -> TraceStore:
    """Vrátí globální TraceStore instanci."""
    global _default_store
    if _default_store is None:
        _default_store = TraceStore()
    return _default_store
