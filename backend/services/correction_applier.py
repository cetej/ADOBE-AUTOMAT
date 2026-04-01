"""Matching a aplikace korektur na textové elementy projektu."""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import logging
from difflib import SequenceMatcher

from services.correction_store import CorrectionEntry

logger = logging.getLogger(__name__)

# Minimální fuzzy shoda pro automatický match
MIN_FUZZY_RATIO = 0.85


def match_corrections(entries: list[CorrectionEntry], elements: list) -> list[CorrectionEntry]:
    """Spáruje correction entries s elementy projektu.

    Pro entries s element_id="" hledá match podle textu.
    Vrací entries s vyplněným element_id a confidence.
    """
    # Lookup tabulky
    exact_lookup: dict[str, str] = {}       # czech.strip() → element_id
    normalized_lookup: dict[str, str] = {}  # czech.strip().lower() → element_id
    elements_by_id: dict[str, str] = {}     # element_id → czech

    for el in elements:
        if not el.czech:
            continue
        eid = el.id
        cz = el.czech.strip()
        exact_lookup[cz] = eid
        normalized_lookup[cz.lower()] = eid
        elements_by_id[eid] = cz

    matched = []
    for entry in entries:
        # Už má element_id (manuální zadání)
        if entry.element_id:
            if entry.element_id in elements_by_id:
                entry.before = elements_by_id[entry.element_id]
                entry.confidence = 1.0
            else:
                entry.confidence = 0.0
                entry.notes = (entry.notes or "") + " [element nenalezen]"
            matched.append(entry)
            continue

        before = entry.before.strip()
        if not before:
            matched.append(entry)
            continue

        # 1. Exact match
        if before in exact_lookup:
            entry.element_id = exact_lookup[before]
            entry.confidence = 1.0
            matched.append(entry)
            continue

        # 2. Normalized match
        before_lower = before.lower()
        if before_lower in normalized_lookup:
            entry.element_id = normalized_lookup[before_lower]
            entry.confidence = 0.95
            matched.append(entry)
            continue

        # 3. Fuzzy match
        best_ratio = 0.0
        best_id = ""
        for cz, eid in exact_lookup.items():
            ratio = SequenceMatcher(None, before, cz).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_id = eid

        if best_ratio >= MIN_FUZZY_RATIO:
            entry.element_id = best_id
            entry.confidence = round(best_ratio, 3)
            matched.append(entry)
            continue

        # Nespárováno
        entry.confidence = round(best_ratio, 3) if best_ratio > 0 else 0.0
        entry.notes = (entry.notes or "") + " [nespárováno]"
        matched.append(entry)

    return matched


def apply_corrections(entries: list[CorrectionEntry], elements: list) -> dict:
    """Aplikuje spárované korektury na elementy.

    Modifikuje elements in-place (elem.czech = entry.after).

    Returns:
        dict s výsledky: applied, skipped, unmatched
    """
    elements_by_id = {el.id: el for el in elements}
    applied = 0
    skipped = 0
    unmatched = 0

    for entry in entries:
        if not entry.element_id or entry.element_id not in elements_by_id:
            unmatched += 1
            continue

        if not entry.after.strip():
            skipped += 1
            continue

        el = elements_by_id[entry.element_id]
        old_czech = el.czech or ""
        el.czech = entry.after
        applied += 1
        logger.debug("Korektura %s: '%s' → '%s'",
                      entry.element_id, old_czech[:40], entry.after[:40])

    stats = {"applied": applied, "skipped": skipped, "unmatched": unmatched}
    logger.info("Korektury aplikovány: %s", stats)
    return stats
