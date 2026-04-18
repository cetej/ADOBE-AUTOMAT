"""Glossary Enforcer — deterministická post-LLM substituce proti termdb.db.

Princip (inspirováno NG-ROBOT Phase 1.5 glossary_enforcer.py):
1. Pro každý přeložený element: EXACT SQL lookup originálu v termdb.db (246K+)
2. Pokud DB zná kanonický CZ překlad a aktuální LLM výstup NENÍ v žádné z variant → přepsat
3. Žádný per-article cache, žádný LLM, žádný fuzzy search — čistá SQL exact-match substituce

POZOR: Nepoužívá NormalizedTermDB.batch_translate() ani .lookup() — ty dělají LIKE '%x%'
substring search a vrací falešné pozitivy (např. 'London' → 'pamlok omejský' přes
salamandra 'Batrachuperus londongensis'). Enforcer musí být EXACT MATCH.

Kontext ADOBE-AUTOMAT:
- Elementy jsou krátké (1–15 slov): popisky map, nadpisy, legendy, datace
- Typicky 1 element = 1 termín → per-element exact match
- Zachovat ALL CAPS pokud byl v originále (IDML layout)
- Pokud DB má více CS variant (synonyma) a LLM vrátí jednu z nich → neměnit
"""

import logging
import re
import sqlite3
from pathlib import Path

from config import MULTI_DOMAIN_DB_PATH
from models import TextElement

logger = logging.getLogger(__name__)

_db_path = MULTI_DOMAIN_DB_PATH if Path(MULTI_DOMAIN_DB_PATH).exists() else None

# DB občas obsahuje "meta-anotované" varianty — závorky s poznámkou, lomítkové alternativy.
# Enforcer je nesmí přebírat jako kanonikum — odfiltrujeme je.
_NOISY_PAREN = re.compile(r'\([^)]{4,}\)')


def _match_case(original_en: str, canonical_cz: str) -> str:
    """Zachová case stylu originálu (ALL CAPS / Title / lower).

    ADOBE-AUTOMAT: IDML layout často vynucuje ALL CAPS — překladatel to má zachovat,
    ale DB vrací lowercase kanonikum. Enforcer musí case přenést.
    """
    if len(original_en) < 2 or not canonical_cz:
        return canonical_cz
    alpha = [c for c in original_en if c.isalpha()]
    if len(alpha) >= 2 and all(c.isupper() for c in alpha):
        return canonical_cz.upper()
    if original_en[:1].isupper() and not (len(original_en) > 1 and original_en[1].isupper()):
        return canonical_cz[:1].upper() + canonical_cz[1:]
    return canonical_cz


def _normalize(s: str) -> str:
    return " ".join((s or "").split()).strip().lower()


def _is_clean_variant(variant: str) -> bool:
    """Je varianta čistý překlad bez meta-anotací?

    Vylučuje:
    - Lomítkové alternativy: 'optimum / perioda' (DB editor neumí ztrátově agregovat)
    - Závorky s poznámkou: 'Brattahlíð (ponechat, historický název)'
    """
    if not variant:
        return False
    if "/" in variant:
        return False
    if _NOISY_PAREN.search(variant):
        return False
    return True


def _lookup_cs_variants(conn: sqlite3.Connection, term: str) -> list[str]:
    """Vrátí všechny CS překlady pro term (exact match na canonical_name).

    Řazení: is_primary DESC, pak id ASC (první → preferovaný kanonický).
    """
    c = conn.cursor()
    c.execute("""
        SELECT tr.name
        FROM terms t
        JOIN translations tr ON tr.term_id = t.id AND tr.language = 'cs'
        WHERE LOWER(t.canonical_name) = LOWER(?)
        ORDER BY tr.is_primary DESC, tr.id ASC
    """, (term,))
    return [row[0] for row in c.fetchall()]


def _lookup_cs_via_en(conn: sqlite3.Connection, term: str) -> list[str]:
    """Fallback: exact match na EN translation, ale JEN tam, kde canonical_name
    se shoduje s EN (chrání před 'Augsburg (a city in Germany)' kde je Germany jen v popisu).
    """
    c = conn.cursor()
    c.execute("""
        SELECT tr_cs.name
        FROM terms t
        JOIN translations tr_en ON tr_en.term_id = t.id AND tr_en.language = 'en'
        JOIN translations tr_cs ON tr_cs.term_id = t.id AND tr_cs.language = 'cs'
        WHERE LOWER(tr_en.name) = LOWER(?)
          AND LOWER(t.canonical_name) = LOWER(tr_en.name)
        ORDER BY tr_cs.is_primary DESC, tr_cs.id ASC
    """, (term,))
    return [row[0] for row in c.fetchall()]


def enforce_glossary_on_results(
    elements: list[TextElement],
    results: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Post-LLM DB enforce nad výsledky translate_batch.

    Args:
        elements: Originální elementy (id → contents EN)
        results: Výsledky překladu [{"id": "...", "czech": "..."}]

    Returns:
        (přepsané results, fix log)
    """
    if not _db_path:
        return results, []

    id_to_en = {el.id: (el.contents or "").strip() for el in elements if el.contents}
    if not any(id_to_en.values()):
        return results, []

    fixes: list[dict] = []
    new_results: list[dict] = []

    try:
        conn = sqlite3.connect(str(_db_path))
    except sqlite3.Error as e:
        logger.warning("glossary_enforcer: DB open failed (%s) — skip", e)
        return results, []

    try:
        for r in results:
            elem_id = r.get("id")
            current_cz = (r.get("czech") or "").strip()
            en = id_to_en.get(elem_id, "")

            if not en or not current_cz:
                new_results.append(r)
                continue

            # Krátké tokeny (≤3 znaky) jsou riziková — stopwords, předložky, layout zkratky
            # V DB se vyskytují zrcadlové záznamy (cs=en), které by enforcer aplikoval jako identitu
            if len(en) < 4:
                new_results.append(r)
                continue

            # 1) Exact canonical_name match
            variants = _lookup_cs_variants(conn, en)
            # 2) Fallback přes EN alias (kde canonical_name == EN translation)
            if not variants:
                variants = _lookup_cs_via_en(conn, en)

            if not variants:
                new_results.append(r)
                continue

            # Odfiltruj zrcadlové záznamy (cs == en case-insensitive) — DB někdy ukládá
            # anglické slovo jako vlastní "překlad" (např. 'of'→'OF', 'is'→'IS')
            variants = [v for v in variants if _normalize(v) != _normalize(en)]
            # Odfiltruj meta-anotované varianty (závorky s poznámkou, lomítkové alternativy)
            variants = [v for v in variants if _is_clean_variant(v)]
            if not variants:
                new_results.append(r)
                continue

            # LLM výstup je mezi DB variantami (synonymum) → neměnit
            variant_norms = {_normalize(v) for v in variants}
            if _normalize(current_cz) in variant_norms:
                new_results.append(r)
                continue

            # Přepsat na primární (první) CS variantu
            canon_cz = variants[0]
            enforced_cz = _match_case(en, canon_cz)

            fixes.append({
                "element_id": elem_id,
                "en": en,
                "was": current_cz,
                "now": enforced_cz,
                "canonical_cz": canon_cz,
                "variants_count": len(variants),
                "source": "glossary_enforcer",
            })
            new_results.append({**r, "czech": enforced_cz})
    finally:
        conn.close()

    if fixes:
        logger.info("glossary_enforcer: %d/%d překladů vynuceno z termdb.db",
                    len(fixes), len(results))

    return new_results, fixes


def enforce_glossary_on_elements(elements: list[TextElement]) -> list[dict]:
    """Inline varianta — přepisuje el.czech přímo. Používá se v audit/retroaktivní modu.

    Returns:
        fix log
    """
    results = [{"id": el.id, "czech": el.czech} for el in elements if el.czech]
    new_results, fixes = enforce_glossary_on_results(elements, results)
    if not fixes:
        return []

    result_map = {r["id"]: r["czech"] for r in new_results}
    for el in elements:
        if el.id in result_map:
            el.czech = result_map[el.id]
    return fixes
