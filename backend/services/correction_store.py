"""CRUD operace pro kola korektur — JSON soubory v data/projects/{id}/corrections/."""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import logging
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

from config import PROJECTS_DIR

logger = logging.getLogger(__name__)


@dataclass
class CorrectionEntry:
    """Jedna oprava v kolu korektur."""
    element_id: str = ""
    before: str = ""
    after: str = ""
    source: str = "manual"       # manual | excel | docx | pdf
    confidence: float = 1.0
    notes: Optional[str] = None


@dataclass
class CorrectionRound:
    """Jedno kolo korektur."""
    round_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    source_file: Optional[str] = None
    source_type: str = "manual"  # manual | excel | docx | pdf
    entries: list[CorrectionEntry] = field(default_factory=list)
    applied: bool = False
    output_key: Optional[str] = None
    stats: dict = field(default_factory=dict)


def _corrections_dir(project_id: str) -> Path:
    """Vrátí cestu ke corrections adresáři projektu."""
    d = PROJECTS_DIR / project_id / "corrections"
    d.mkdir(parents=True, exist_ok=True)
    return d


def next_round_id(project_id: str) -> str:
    """Vrátí další round_id (r01, r02, ...)."""
    d = _corrections_dir(project_id)
    existing = sorted(d.glob("r*.json"))
    if not existing:
        return "r01"
    last = existing[-1].stem  # e.g. "r03"
    num = int(last[1:]) + 1
    return f"r{num:02d}"


def save_round(project_id: str, round_data: CorrectionRound) -> Path:
    """Uloží kolo korektur jako JSON."""
    d = _corrections_dir(project_id)
    path = d / f"{round_data.round_id}.json"

    data = asdict(round_data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Uloženo kolo korektur %s → %s", round_data.round_id, path)
    return path


def get_round(project_id: str, round_id: str) -> Optional[CorrectionRound]:
    """Načte jedno kolo korektur."""
    path = _corrections_dir(project_id) / f"{round_id}.json"
    if not path.exists():
        return None

    data = json.loads(path.read_text(encoding="utf-8"))
    entries = [CorrectionEntry(**e) for e in data.get("entries", [])]
    data["entries"] = entries
    return CorrectionRound(**data)


def get_rounds(project_id: str) -> list[CorrectionRound]:
    """Načte všechna kola korektur (bez plných entries pro rychlost)."""
    d = _corrections_dir(project_id)
    rounds = []
    for path in sorted(d.glob("r*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            # Pro listing: entries nahradíme počtem
            entry_count = len(data.get("entries", []))
            data["entries"] = []
            r = CorrectionRound(**data)
            r.stats["entry_count"] = entry_count
            rounds.append(r)
        except Exception as e:
            logger.warning("Chyba čtení %s: %s", path, e)
    return rounds
