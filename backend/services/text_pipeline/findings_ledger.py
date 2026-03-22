"""Findings ledger — cross-phase state accumulator.

Adapted from NG-ROBOT ngrobot.py. Akumuluje zjištění z fází 3-5,
aby pozdější fáze nepřepisovaly práci dřívějších.
"""

import re
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_findings_ledger(project_dir: Path) -> dict:
    """Načte findings ledger pro projekt."""
    ledger_file = project_dir / "findings_ledger.json"
    if not ledger_file.exists():
        return {}
    try:
        return json.loads(ledger_file.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        return {}


def save_findings_ledger(project_dir: Path, ledger: dict):
    """Uloží findings ledger."""
    ledger_file = project_dir / "findings_ledger.json"
    ledger_file.write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )


def update_findings_ledger(project_dir: Path, phase: int, content: str):
    """Extrahuje zjištění z výstupu fáze a přidá do ledgeru."""
    ledger = load_findings_ledger(project_dir)
    findings = _extract_phase_findings(phase, content)
    if findings:
        ledger[f"phase_{phase}"] = findings
        save_findings_ledger(project_dir, ledger)


def _extract_phase_findings(phase: int, content: str) -> dict:
    """Extrahuje klíčová zjištění z výstupu fáze."""
    findings = {}

    if phase == 3:
        # Terminologické opravy
        corrections = []
        for match in re.finditer(
            r'\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|',
            content
        ):
            orig, corrected, source = (
                match.group(1).strip(),
                match.group(2).strip(),
                match.group(3).strip()
            )
            if orig.startswith('---') or orig.lower() in ('původní', 'originál', 'original', 'termín'):
                continue
            if orig != corrected:
                corrections.append({
                    "original": orig,
                    "corrected": corrected,
                    "source": source[:80]
                })
        if corrections:
            findings["corrections"] = corrections[:30]

    elif phase == 4:
        # Převody jednotek
        unit_conversions = []
        for match in re.finditer(
            r'(\d[\d\s,.]*\s*(?:mil[eí]?|feet|ft|°F|fahrenheit|libr[ay]?|lb|yard[sů]?|yd|USD|\$))\s*[→→=]\s*([^\n|]+)',
            content, re.IGNORECASE
        ):
            unit_conversions.append({
                "original": match.group(1).strip(),
                "converted": match.group(2).strip()[:50]
            })
        if unit_conversions:
            findings["unit_conversions"] = unit_conversions[:20]

        # Faktické opravy
        fact_fixes = []
        for match in re.finditer(
            r'\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|',
            content
        ):
            orig, fixed, reason = (
                match.group(1).strip(),
                match.group(2).strip(),
                match.group(3).strip()
            )
            if orig.startswith('---') or orig.lower() in ('původní', 'originál', 'chyba', 'original'):
                continue
            if orig != fixed and len(orig) > 3:
                fact_fixes.append({"original": orig[:80], "corrected": fixed[:80]})
        if fact_fixes:
            findings["fact_corrections"] = fact_fixes[:20]

    elif phase == 5:
        # False friends
        false_friends = []
        for match in re.finditer(
            r'(?:false\s*friend|překladová\s*past)[^|]*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|',
            content, re.IGNORECASE
        ):
            false_friends.append({
                "wrong": match.group(1).strip(),
                "correct": match.group(2).strip()
            })
        if false_friends:
            findings["false_friends"] = false_friends[:15]

    return findings


def format_findings_for_phase(ledger: dict, target_phase: int) -> str:
    """Formátuje zjištění z ledgeru jako kontextový prefix."""
    if not ledger:
        return ""

    parts = []

    # Fáze 5+ dostávají ověřené termíny z fáze 3
    if target_phase >= 5 and "phase_3" in ledger:
        p3 = ledger["phase_3"]
        if p3.get("corrections"):
            terms = [f"{c['corrected']}" for c in p3["corrections"][:15]]
            parts.append(f"OVĚŘENÉ TERMÍNY (fáze 3) — NEMĚNIT: {', '.join(terms)}")

    # Fáze 5+ dostávají převody z fáze 4
    if target_phase >= 5 and "phase_4" in ledger:
        p4 = ledger["phase_4"]
        if p4.get("unit_conversions"):
            conversions = [f"{c['original']} → {c['converted']}" for c in p4["unit_conversions"][:10]]
            parts.append(f"OVĚŘENÉ PŘEVODY (fáze 4) — ZACHOVAT: {'; '.join(conversions)}")

    # Fáze 6+ dostávají jazykové opravy z fáze 5
    if target_phase >= 6 and "phase_5" in ledger:
        p5 = ledger["phase_5"]
        if p5.get("false_friends"):
            ff = [f"NE '{c['wrong']}' → ANO '{c['correct']}'" for c in p5["false_friends"][:10]]
            parts.append(f"PŘEKLADOVÉ PASTI (fáze 5) — OVĚŘENO: {'; '.join(ff)}")

    if not parts:
        return ""

    return "---\nZJIŠTĚNÍ Z PŘEDCHOZÍCH FÁZÍ (findings ledger):\n" + "\n".join(f"- {p}" for p in parts) + "\n---\n\n"
