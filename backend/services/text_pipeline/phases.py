"""Text processing phases — adapted from NG-ROBOT claude_processor.py.

Phase 2: CompletenessChecker — kontrola úplnosti překladu
Phase 3: TermVerifier — ověření termínů (2-call: Research → Apply)
Phase 4: FactChecker — kontrola faktů + jednotky (2-call: Audit → Verify & Apply)
Phase 5: LanguageContextOptimizer — jazyk, false friends, anglicismy, typografie
Phase 6: StylisticEditor — stylistika (Opus)
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import Optional, List

from .processor import (
    ClaudeProcessor, ProcessingResult,
    MODEL_OPUS, MODEL_SONNET, MODEL_HAIKU,
)

logger = logging.getLogger(__name__)

# Cesty k prompt souborům — zkopírované z NG-ROBOT projects/
PROMPTS_DIR = Path(__file__).parent / "prompts"


# === Sanitizace výstupu — brání prosakování reasoning/metadat do článku ===

# Protokolové hlavičky, které model generuje ale nepatří do textu
_PROTOCOL_HEADERS = (
    "PROVEDENÉ DOPLNĚNÍ A OPRAVY", "PROVEDENÉ DOPLNĚNÍ", "PROVEDENÉ OPRAVY",
    "TERMINOLOGICKÉ OPRAVY", "FAKTICKÉ OPRAVY", "JAZYKOVÉ A KONTEXTOVÉ OPRAVY",
    "STYLISTICKÉ ÚPRAVY", "VERIFICATION LOG", "SHRNUTÍ OPRAV", "SHRNUTÍ",
    "ZJIŠTĚNÍ Z PŘEDCHOZÍCH FÁZÍ", "OVĚŘENÉ TERMÍNY", "AUDIT STATISTIKY",
    "POCHYBNÁ FAKTA K OVĚŘENÍ", "OPRAVENÝ TEXT ČLÁNKU",
)

# Reasoning fráze (CZ/EN), které model občas vmíchá do textu
_REASONING_PATTERNS = [
    r"^(?:Nyní|Nejprve|Mám dostatek|Klíčová oprava|Sestavím|Provedu|Zkontrol).*$",
    r"^(?:Now I|Let me|I'll|I need to|I have enough|Key correction).*$",
    r"^---+\s*$",  # samotné oddělovače
]


def sanitize_article_text(text: str) -> str:
    """Odstraní reasoning, protokolové hlavičky a metadata z textu článku.

    Inspirováno NG-ROBOT core.py:sanitize_article_text() — defence-in-depth
    proti prosakování interních poznámek modelu do výstupu pipeline.
    """
    if not text:
        return text

    # 1. Odstraň protokolové sekce (## FAKTICKÉ OPRAVY ... až do dalšího ## nebo konce)
    for header in _PROTOCOL_HEADERS:
        text = re.sub(
            rf'^## {re.escape(header)}.*?(?=\n## [A-ZÁČĎĚÍŇÓŘŠŤÚŮÝŽ]|\Z)',
            '', text, flags=re.MULTILINE | re.DOTALL
        )

    # 2. Odstraň findings ledger echo
    text = re.sub(
        r'------ZJIŠTĚNÍ Z PŘEDCHOZÍCH FÁZÍ.*?(?=<!--\[elem-|\Z)',
        '', text, flags=re.DOTALL
    )
    text = re.sub(
        r'---\s*\n\s*ZJIŠTĚNÍ Z PŘEDCHOZÍCH FÁZÍ.*?(?=<!--\[elem-|\Z)',
        '', text, flags=re.DOTALL
    )

    # 3. Odstraň inline reasoning fráze
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        skip = False
        for pattern in _REASONING_PATTERNS:
            if re.match(pattern, line.strip()):
                # Ale zachovej pokud je uvnitř elementu (legitimní text článku)
                if '<!--[elem-' not in line and '<!--[/elem-' not in line:
                    skip = True
                    break
        if not skip:
            cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)

    # 4. Odstraň PATCH syntax pokud pronikla do textu
    text = re.sub(r'^### PATCH \d+:.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^(?:REPLACE|WITH|INSERT|DELETE|AFTER|END_PATCH):.*$', '', text, flags=re.MULTILINE)

    # 5. Collapse prázdné řádky (max 2 za sebou)
    text = re.sub(r'\n{4,}', '\n\n\n', text)

    return text.strip()

# --- Terminologické utility ---

# Graceful import ngm-terminology — JEDINÝ ZDROJ: termdb.db (246K+ termínů)
try:
    from ngm_terminology import NormalizedTermDB
    from config import MULTI_DOMAIN_DB_PATH
    _main_db = None

    _main_db_path = Path(MULTI_DOMAIN_DB_PATH)
    if _main_db_path.exists():
        try:
            _main_db = NormalizedTermDB(str(_main_db_path))
        except Exception:
            pass

    TERMDB_AVAILABLE = _main_db is not None
except ImportError:
    TERMDB_AVAILABLE = False
    _main_db = None

# CorrectorRulesDB
try:
    from ngm_terminology.corrector_rules import CorrectorRulesDB
    CORRECTOR_RULES_AVAILABLE = True
except ImportError:
    CORRECTOR_RULES_AVAILABLE = False


def format_termdb_for_prompt(max_terms: int = 100,
                              article_domains: Optional[List[str]] = None) -> str:
    """Formátuje termdb.db (246K+ termínů) jako markdown kontext."""
    if not _main_db:
        return ""

    parts = []
    _domain_categories = {
        'geography': ['country', 'sea', 'river', 'mountain_range', 'lake', 'island'],
        'geology': ['mineral', 'rock', 'geological_period'],
        'chemistry': ['element', 'compound'],
        'medicine': ['disease', 'anatomy', 'organ'],
        'astronomy': ['constellation', 'planet', 'nebula'],
        'biology': ['species'],
    }
    _domain_labels = {
        'geography': 'GEOGRAFIE', 'geology': 'GEOLOGIE',
        'chemistry': 'CHEMIE', 'medicine': 'MEDICÍNA',
        'astronomy': 'ASTRONOMIE', 'biology': 'BIOLOGIE',
        'general': 'OBECNÉ', 'encyclopedia': 'ENCYKLOPEDICKÉ',
    }

    domains = list(article_domains or ['biology'])
    if 'biology' not in domains:
        domains.insert(0, 'biology')

    try:
        for domain in domains:
            cats = _domain_categories.get(domain)
            table = _main_db.format_for_prompt(max_terms=max_terms, domain=domain, categories=cats)
            if table:
                label = _domain_labels.get(domain, domain.upper())
                parts.append(
                    f"## OVĚŘENÉ TERMÍNY — {label} (termdb.db, 246K+)\n"
                    f"Tyto termíny jsou ověřené — NEMUSÍŠ je ověřovat web searchem:\n\n{table}\n"
                )
    except Exception:
        pass

    if not parts:
        return ""

    result = '\n'.join(parts)
    result += "\nUšetřené web searches věnuj NOVÝM termínům.\n\n---\n"
    return result


def format_corrector_rules_for_prompt(max_per_category: int = 20) -> str:
    """Formátuje CorrectorRulesDB jako markdown kontext."""
    if not CORRECTOR_RULES_AVAILABLE:
        return ""
    try:
        db = CorrectorRulesDB()
        result = db.format_for_prompt(max_per_category=max_per_category)
        db.close()
        if result and result.strip():
            return f"\n\n---\n\n# DATABÁZE KOREKČNÍCH PRAVIDEL\n\n{result}"
        return ""
    except Exception:
        return ""


def detect_domains_from_text(text: str) -> List[str]:
    """Detekuje relevantní domény z textu článku."""
    text_lower = text.lower()

    domain_keywords = {
        'geography': ['geograf', 'continent', 'countr', 'river', 'mountain', 'ocean',
                       'sea', 'island', 'lake', 'map', 'region', 'krajin', 'pohoří',
                       'řeka', 'jezero', 'ostrov', 'moře', 'oceán'],
        'geology': ['geolog', 'mineral', 'rock', 'fossil', 'volcano', 'earthquake',
                     'sopka', 'zemětřes', 'minerál', 'hornin', 'fosili'],
        'chemistry': ['chemi', 'molecule', 'element', 'compound', 'prvek', 'sloučenin'],
        'medicine': ['medic', 'disease', 'health', 'virus', 'bacteria', 'cancer',
                      'nemoc', 'léčb', 'medicín', 'zdraví'],
        'astronomy': ['astron', 'planet', 'star', 'galaxy', 'nebula',
                       'hvězd', 'planeta', 'galaxi', 'vesmír'],
        'biology': ['biolog', 'species', 'animal', 'plant', 'ecosystem',
                     'druh', 'živočich', 'rostlin', 'ekosystém', 'biodiv'],
    }

    detected = []
    for domain, keywords in domain_keywords.items():
        if any(kw in text_lower for kw in keywords):
            detected.append(domain)

    return detected


# ============================================================
# PATCH formát utility — model vrací jen opravy, ne celý text
# ============================================================

def _apply_patches(original_text: str, patch_output: str, summary_header: str = "PROVEDENÉ DOPLNĚNÍ") -> str:
    """Aplikuje PATCH bloky na originální text překladu.

    PATCH formát eliminuje riziko sumarizace (Sonnet 4.6 s thinking:disabled)
    a chrání <!--[elem-...]-->  markery (model je nevidí = nemůže je poškodit).
    """
    text = original_text

    patches = re.split(r'### PATCH \d+:', patch_output)

    applied = 0
    for patch_block in patches[1:]:  # Skip text before first PATCH
        patch_block = patch_block.strip()

        # INSERT after
        after_match = re.search(r'AFTER:\s*(.+?)(?:\n)', patch_block)
        insert_match = re.search(r'INSERT:\n(.*?)(?:\nEND_PATCH|$)', patch_block, re.DOTALL)
        if after_match and insert_match:
            anchor = after_match.group(1).strip()
            insert_text = insert_match.group(1).strip()
            if anchor in text:
                text = text.replace(anchor, anchor + '\n\n' + insert_text, 1)
                applied += 1
            continue

        # REPLACE
        replace_match = re.search(r'REPLACE:\s*(.+?)(?:\nWITH:)', patch_block, re.DOTALL)
        with_match = re.search(r'WITH:\n(.*?)(?:\nEND_PATCH|$)', patch_block, re.DOTALL)
        if replace_match and with_match:
            old_text = replace_match.group(1).strip()
            new_text = with_match.group(1).strip()
            if old_text in text:
                text = text.replace(old_text, new_text, 1)
                applied += 1
            continue

        # DELETE
        delete_match = re.search(r'DELETE:\s*(.+?)(?:\nEND_PATCH|$)', patch_block, re.DOTALL)
        if delete_match:
            del_text = delete_match.group(1).strip()
            if del_text in text:
                text = text.replace(del_text, '', 1)
                applied += 1

    # Přidej shrnutí na konec
    summary_match = re.search(r'## (?:SHRNUTÍ|' + re.escape(summary_header) + r')\n(.*?)$', patch_output, re.DOTALL)
    summary = summary_match.group(0) if summary_match else f"## {summary_header}\n- Aplikováno {applied} oprav"
    text = text.rstrip() + '\n\n---\n\n' + summary

    return text


# ============================================================
# Phase 2: Kontrola úplnosti překladu
# ============================================================

class CompletenessChecker(ClaudeProcessor):
    """Kontrola úplnosti překladu — porovnání s originálem."""

    DEFAULT_MODEL = MODEL_SONNET
    EFFORT = "low"
    DISABLE_THINKING = True
    MAX_TOKENS = 32000

    def check_completeness(self, original: str, translation: str) -> ProcessingResult:
        """Zkontroluje úplnost překladu a doplní chybějící části.

        Používá PATCH formát — model vrací jen opravy, ne celý text.
        Eliminuje riziko sumarizace a ztráty <!--[elem-...]--> markerů.

        Args:
            original: Originální anglický text
            translation: Český překlad (spojený z elementů se značkami)

        Returns:
            ProcessingResult s opraveným překladem (se zachovanými značkami)
        """
        content = f"""# ORIGINÁL (ANGLIČTINA)

{original}

---

# PŘEKLAD (ČEŠTINA)

{translation}
"""
        instruction = """TVÝM ÚKOLEM JE ZKONTROLOVAT PŘEKLAD A VRÁTIT OPRAVY VE FORMÁTU PATCH.

⚠️ NEREPRODUKUJ CELÝ TEXT! Vrať JEN opravy v PATCH formátu.

POSTUP:
1. Porovnej originál s překladem — identifikuj VŠECHNY chybějící části
2. Pro každou chybějící část vytvoř PATCH blok

VÝSTUPNÍ FORMÁT (PATCH bloky):

Pokud je překlad kompletní a bez chyb, vrať:
ŽÁDNÉ OPRAVY

Pokud jsou potřeba opravy, vrať PATCH bloky:

### PATCH 1:
AFTER: [přesný text v překladu, za který se vloží nový obsah]
INSERT:
[přeložený chybějící text]
END_PATCH

### PATCH 2:
REPLACE: [přesný existující text k nahrazení]
WITH:
[opravený text]
END_PATCH

### PATCH 3:
DELETE: [přesný text k odstranění]
END_PATCH

## PROVEDENÉ DOPLNĚNÍ
- [seznam provedených změn]

PRAVIDLA:
- AFTER/REPLACE/DELETE musí být PŘESNÉ kopie textu z překladu (case-sensitive)
- Používej dostatečně dlouhé kotvy (min. 15 znaků) pro jednoznačnou identifikaci
- NIKDY neměň <!--[elem-...]--> značky — jsou neviditelné pro tebe
- Každá chybějící část originálu = jeden PATCH blok"""

        projects_dir = PROMPTS_DIR / "2-KONTROLA_UPLNOSTI_PREKLADU"
        result = self.process_with_project(
            content=content,
            project_dir=projects_dir,
            additional_instruction=instruction
        )

        # Aplikuj PATCH bloky na originální překlad
        if result.success and result.content:
            if "ŽÁDNÉ OPRAVY" in result.content:
                result.content = translation + "\n\n---\n\n## PROVEDENÉ DOPLNĚNÍ\n- Překlad je kompletní, žádné opravy."
            elif "### PATCH" in result.content:
                result.content = _apply_patches(translation, result.content, "PROVEDENÉ DOPLNĚNÍ")
            # else: model vrátil neočekávaný formát — ponechat raw output

        return result


# ============================================================
# Phase 3: Ověření termínů (2-call: Research → Apply)
# ============================================================

class TermVerifier(ClaudeProcessor):
    """Ověření odborných termínů — DB-first, web search jen pro neznámé."""

    DEFAULT_MODEL = MODEL_SONNET
    EFFORT = "low"
    DISABLE_THINKING = True
    MAX_TOKENS = 32000
    TERM_SEARCH_MAX_USES = 8  # sníženo — většina se řeší lokálně

    def _research_terms(self, translated_content: str, termdb_context: str = "") -> ProcessingResult:
        """Call 1 (Research): DB kontext z format_termdb_for_prompt + web search jen pro neznámé."""
        db_block = ""
        if termdb_context:
            db_block = f"""{termdb_context}

---

"""

        instruction = f"""TVÝM ÚKOLEM JE IDENTIFIKOVAT A OVĚŘIT ODBORNÉ TERMÍNY V TEXTU.

{db_block}TEXT K ANALÝZE:
{translated_content}

---

## POVINNÝ PROTOKOL OVĚŘOVÁNÍ

⚠️ DŮLEŽITÉ:
- Termíny nalezené v LOKÁLNÍ DATABÁZI (viz výše) NEOVĚŘUJ web searchem — jsou potvrzené.
- Web search POUZE pro termíny, které NEJSOU v lokální DB.
- Text obsahuje HTML značky <!--[elem-...]-->. Tyto značky IGNORUJ při analýze,
  ale ZACHOVEJ je ve výstupu.

### KROK 0: TRIAGE
Roztřiď NEZNÁMÉ termíny (= ne v lokální DB) na HIGH RISK a LOW RISK.

HIGH RISK (ověř web searchem): biologické druhy, méně známé lokality, odborné termíny
LOW RISK (přeskoč): obecně známá zvířata, hlavní města, kontinenty, běžné pojmy

⚠️ Max {self.TERM_SEARCH_MAX_USES} searches — šetři je pro skutečně neznámé termíny.

### Postup pro HIGH RISK biologické druhy:
1. web_search("{{anglický název}} český název site:cs.wikipedia.org OR site:biolib.cz")
2. Wikipedia/NG.cz preference (žurnalistický standard)

### Postup pro ostatní HIGH RISK:
1. web_search("{{termín}} site:cs.wikipedia.org")

### KONTROLNÍ BODY:
- Dva EN termíny → stejný CZ = CHYBA
- Žádný snippet = NEOVĚŘENO
- STOP: 2 neúspěšné hledání pro 1 termín → NEOVĚŘENO

---

⚠️ VÝSTUP: POUZE TABULKA OPRAV — NE CELÝ TEXT!

## TERMINOLOGICKÉ OPRAVY

| # | EN původní | LAT | CZ v textu | CZ správně | Snippet (důkaz) | URL | Poznámka |
|---|---|---|---|---|---|---|---|

## NEOVĚŘENÉ TERMÍNY

| # | EN | Důvod |
|---|---|---|

## STATISTIKY
- Celkem termínů: X
- Ověřeno: Y
- Opraveno: Z
- Web searches: N/{self.TERM_SEARCH_MAX_USES}

DŮLEŽITÉ: NEREPRODUKUJ celý text. Vrať JEN tabulky výše."""

        research_tools = [
            {"type": "code_execution_20260120", "name": "code_execution"},
            {"type": "web_search_20260209", "name": "web_search", "max_uses": self.TERM_SEARCH_MAX_USES},
            {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 5}
        ]

        projects_dir = PROMPTS_DIR / "3-OVERENI_TERMINU"

        # Research config: thinking ON, high effort (medium leakuje CoT do výstupu)
        saved = (self.DISABLE_THINKING, self.EFFORT, self.MAX_TOKENS)
        try:
            self.DISABLE_THINKING = False
            self.EFFORT = "high"
            self.MAX_TOKENS = 16000
            logger.info("[Phase 3 Call 1/2] Research: web search + reasoning")
            return self.process_with_project(
                content="", project_dir=projects_dir,
                additional_instruction=instruction, tools=research_tools
            )
        finally:
            self.DISABLE_THINKING, self.EFFORT, self.MAX_TOKENS = saved

    def _apply_corrections(self, translated_content: str, corrections_table: str) -> ProcessingResult:
        """Call 2 (Apply): mechanická aplikace oprav."""
        instruction = f"""TVÝM ÚKOLEM JE APLIKOVAT TERMINOLOGICKÉ OPRAVY NA TEXT.

## TABULKA OPRAV:

{corrections_table}

---

## TEXT K OPRAVĚ:

{translated_content}

---

## INSTRUKCE:
1. Pro každý řádek kde "CZ v textu" ≠ "CZ správně": nahraď VŠECHNY výskyty
2. Zachovej správný tvar (pád, číslo, rod)
3. Termíny NEOVĚŘENÉ ponech beze změny
4. ZACHOVEJ VŠECHNY <!--[elem-...]--> značky beze změny!
5. ZACHOVEJ celý text beze zkrácení

## VÝSTUP:
1. KOMPLETNÍ TEXT s aplikovanými opravami
2. Na konci ## TERMINOLOGICKÉ OPRAVY z tabulky"""

        logger.info("[Phase 3 Call 2/2] Apply: mechanická aplikace oprav (Haiku)")
        saved_model = self.model
        try:
            self.model = MODEL_HAIKU
            return self.process(
                content=instruction,
                system_prompt="Jsi terminologický korektor. Aplikuješ tabulku oprav na text. ZACHOVEJ všechny <!--[elem-...]--> značky. NIKDY nezkracuj text."
            )
        finally:
            self.model = saved_model

    def verify_terms(self, translated_content: str, termdb_context: str = "") -> ProcessingResult:
        """Ověří termíny (DB kontext v promptu → Research → Apply).

        DB kontext dodává format_termdb_for_prompt() — injektuje ověřené termíny
        z termdb.db (246K+) přímo do promptu. LLM pak ověřuje web searchem
        jen termíny, které v DB nejsou.
        """
        # Call 1: Research — DB kontext v promptu, web search jen pro neznámé
        research_result = self._research_terms(translated_content, termdb_context)
        if not research_result.success:
            logger.error(f"Research selhal: {research_result.error}")
            return research_result

        corrections_table = research_result.content
        if not corrections_table or len(corrections_table.strip()) < 50:
            logger.info("Research vrátil prázdnou tabulku — vracím původní text")
            return ProcessingResult(
                success=True, content=translated_content,
                tokens_used=research_result.tokens_used,
                input_tokens=research_result.input_tokens,
                output_tokens=research_result.output_tokens,
            )

        has_corrections = ("CZ správně" in corrections_table and "CZ v textu" in corrections_table)
        if not has_corrections:
            logger.info("Žádné terminologické opravy")
            return ProcessingResult(
                success=True, content=translated_content,
                tokens_used=research_result.tokens_used,
                input_tokens=research_result.input_tokens,
                output_tokens=research_result.output_tokens,
            )

        # Call 2: Apply
        apply_result = self._apply_corrections(translated_content, corrections_table)
        if not apply_result.success:
            logger.warning(f"Apply selhal: {apply_result.error} — fallback na původní text")
            return ProcessingResult(
                success=True, content=translated_content,
                tokens_used=(research_result.tokens_used or 0) + (apply_result.tokens_used or 0),
                input_tokens=(research_result.input_tokens or 0) + (apply_result.input_tokens or 0),
                output_tokens=(research_result.output_tokens or 0) + (apply_result.output_tokens or 0),
                artifacts={"apply_failed": True, "corrections_table": corrections_table}
            )

        # Fragment check
        if len(apply_result.content) < len(translated_content) * 0.5:
            logger.warning("Apply vrátil fragment — fallback na původní text")
            return ProcessingResult(
                success=True, content=translated_content,
                tokens_used=(research_result.tokens_used or 0) + (apply_result.tokens_used or 0),
                input_tokens=(research_result.input_tokens or 0) + (apply_result.input_tokens or 0),
                output_tokens=(research_result.output_tokens or 0) + (apply_result.output_tokens or 0),
                artifacts={"apply_truncated": True}
            )

        total_tokens = (research_result.tokens_used or 0) + (apply_result.tokens_used or 0)
        total_input = (research_result.input_tokens or 0) + (apply_result.input_tokens or 0)
        total_output = (research_result.output_tokens or 0) + (apply_result.output_tokens or 0)
        all_searches = (research_result.web_searches or []) + (apply_result.web_searches or [])

        return ProcessingResult(
            success=True, content=apply_result.content,
            tokens_used=total_tokens, input_tokens=total_input,
            output_tokens=total_output, truncated=apply_result.truncated,
            web_searches=all_searches,
            artifacts={"corrections_table": corrections_table}
        )


# ============================================================
# Phase 4: Kontrola faktů (2-call: Audit → Verify & Apply)
# ============================================================

class FactChecker(ClaudeProcessor):
    """Kontrola faktů + převod jednotek — 2-call (Audit → Verify & Apply)."""

    DEFAULT_MODEL = MODEL_SONNET
    EFFORT = "low"
    DISABLE_THINKING = True
    MAX_TOKENS = 32000
    FACT_SEARCH_MAX_USES = 10

    def _audit_facts(self, article_content: str) -> ProcessingResult:
        """Call 1 (Audit): identifikace pochybných faktů + převod jednotek."""
        instruction = f"""TVÝM ÚKOLEM JE PROVÉST AUDIT FAKTŮ — identifikovat chyby a navrhnout ověření.

⚠️ Text obsahuje HTML značky <!--[elem-...]-->. IGNORUJ je při analýze.

ČLÁNEK K AUDITU:
{article_content}

---

## POSTUP:

### ÚLOHA A: MECHANICKÉ PŘEVODY
Imperiální jednotky → metrické:
- Míle → km (×1,609), stopy → m (×0,305), °F → °C ((°F−32)×5/9)
- Libry → kg (×0,454), akry → ha (×0,405), sq mi → km² (×2,59)
- USD → Kč (~23 Kč/USD)
- V přímých citacích NEPŘEVÁDĚT

### ÚLOHA B: IDENTIFIKACE POCHYBNÝCH FAKTŮ
- Data, roky, číselné údaje, geografie, chronologie
- Ohodnoť confidence (0.0–1.0) a navrhni search query

⚠️ CO NEPATŘÍ: terminologie (řeší fáze 3), stylistika (řeší fáze 5/6)

---

## VÝSTUP: POUZE TABULKY

## PROVEDENÉ OPRAVY (jednotky a měny)
| # | Původní text | Opravený text | Typ |
|---|---|---|---|

## POCHYBNÁ FAKTA K OVĚŘENÍ
| # | Tvrzení v článku | Confidence | Search query | Kategorie |
|---|---|---|---|---|

## AUDIT STATISTIKY
- Převodů jednotek: X
- Pochybných faktů: Y

DŮLEŽITÉ: NEREPRODUKUJ celý článek. Vrať JEN tabulky."""

        projects_dir = PROMPTS_DIR / "4-KONTROLA_FAKT"

        saved = (self.DISABLE_THINKING, self.EFFORT, self.MAX_TOKENS)
        try:
            self.DISABLE_THINKING = False
            self.EFFORT = "high"
            self.MAX_TOKENS = 16000
            logger.info("[Phase 4 Call 1/2] Audit: reasoning bez tools")
            return self.process_with_project(
                content="", project_dir=projects_dir,
                additional_instruction=instruction
            )
        finally:
            self.DISABLE_THINKING, self.EFFORT, self.MAX_TOKENS = saved

    PATCH_INSTRUCTION = """
⚠️ NEREPRODUKUJ CELÝ ČLÁNEK! Vrať POUZE PATCH — seznam oprav.

FORMÁT VÝSTUPU — PATCH BLOKY:

### PATCH 1: [popis opravy]
REPLACE: [přesná citace chybného textu z článku, min. 20 znaků, UNIKÁTNÍ v textu]
WITH: [opravený text]
END_PATCH

### PATCH 2: [popis]
REPLACE: [přesná citace]
WITH: [oprava]
END_PATCH

Pokud žádné opravy nejsou potřeba, vrať:
### NO PATCHES
Žádné faktické chyby nenalezeny.

## SHRNUTÍ
- Počet oprav: X
"""

    def _verify_and_apply(self, article_content: str, audit_table: str) -> ProcessingResult:
        """Call 2 (Verify): web search → PATCH bloky (model NEREPRODUKUJE článek)."""
        instruction = f"""TVÝM ÚKOLEM JE OVĚŘIT POCHYBNÁ FAKTA A VRÁTIT OPRAVY JAKO PATCH BLOKY.

## AUDIT (výsledky z Call 1):
{audit_table}

---

## ČLÁNEK (pouze pro referenci — NEREPRODUKUJ ho):
{article_content}

---

## INSTRUKCE:
1. Ověř pochybná fakta z tabulky web searchem
2. Pro každý potvrzený problém (špatný fakt, chybějící převod jednotek) vytvoř PATCH
3. REPLACE musí být přesná citace z článku (min. 20 znaků, unikátní)
4. Ignoruj <!--[elem-...]--> značky v citacích — jsou součástí textu
5. NIKDY nereprodukuj celý článek

{self.PATCH_INSTRUCTION}"""

        verify_tools = [
            {"type": "web_search_20260209", "name": "web_search", "max_uses": self.FACT_SEARCH_MAX_USES}
        ]

        saved_max = self.MAX_TOKENS
        self.MAX_TOKENS = 16000  # PATCH bloky jsou malé

        try:
            logger.info("[Phase 4 Call 2/2] Verify: web search → PATCH bloky")
            return self.process(
                content=instruction,
                system_prompt="Jsi faktický korektor. Ověřuješ fakta web searchem. NIKDY nereprodukuj celý článek. Výstup = POUZE PATCH bloky.",
                tools=verify_tools
            )
        finally:
            self.MAX_TOKENS = saved_max

    @staticmethod
    def _apply_patches(original_text: str, patch_output: str) -> tuple[str, list[dict]]:
        """Deterministicky aplikuje PATCH bloky na originální text.

        Returns:
            (patched_text, report) — report = [{"patch": N, "desc": ..., "status": "applied"|"skipped"}]
        """
        text = original_text
        report = []

        # Rozděl na jednotlivé PATCH bloky
        patches = re.split(r'### PATCH \d+:', patch_output)

        for i, patch_block in enumerate(patches[1:], 1):
            lines = patch_block.strip().split('\n')
            desc = lines[0].strip() if lines else f"Patch {i}"

            # Parse REPLACE/WITH
            replace_match = re.search(
                r'REPLACE:\s*(.+?)(?:\nWITH:\s*(.+?))?(?:\nEND_PATCH|$)',
                patch_block, re.DOTALL
            )

            if not replace_match:
                report.append({"patch": i, "desc": desc, "status": "skipped", "reason": "parse error"})
                continue

            old_text = replace_match.group(1).strip()
            new_text = (replace_match.group(2) or "").strip()

            if not old_text:
                report.append({"patch": i, "desc": desc, "status": "skipped", "reason": "empty REPLACE"})
                continue

            # Aplikuj — přesný string replace (max 1 výskyt)
            if old_text in text:
                text = text.replace(old_text, new_text, 1)
                report.append({"patch": i, "desc": desc, "status": "applied"})
                logger.info("PATCH %d applied: %s", i, desc)
            else:
                # Zkus fuzzy — ignoruj whitespace rozdíly
                normalized_old = re.sub(r'\s+', ' ', old_text)
                normalized_text = re.sub(r'\s+', ' ', text)
                if normalized_old in normalized_text:
                    # Najdi pozici v originálním textu
                    pos = normalized_text.find(normalized_old)
                    # Rekonstruuj boundaries v originálním textu
                    # (jednoduchý přístup — nahraď v normalizovaném a reconstruct)
                    text = text.replace(old_text.split()[0], new_text.split()[0] if new_text else "", 1)
                    report.append({"patch": i, "desc": desc, "status": "applied-fuzzy"})
                    logger.info("PATCH %d applied (fuzzy): %s", i, desc)
                else:
                    report.append({"patch": i, "desc": desc, "status": "skipped", "reason": "not found"})
                    logger.warning("PATCH %d skipped (not found): '%s...'", i, old_text[:50])

        return text, report

    def check_facts(self, article_content: str) -> ProcessingResult:
        """Zkontroluje fakta (Audit → Verify & Apply)."""
        # Call 1: Audit
        audit_result = self._audit_facts(article_content)
        if not audit_result.success:
            logger.error(f"Audit selhal: {audit_result.error}")
            return audit_result

        audit_table = audit_result.content
        if not audit_table or len(audit_table.strip()) < 50:
            return ProcessingResult(
                success=True, content=article_content,
                tokens_used=audit_result.tokens_used,
                input_tokens=audit_result.input_tokens,
                output_tokens=audit_result.output_tokens,
            )

        has_work = ("PROVEDENÉ OPRAVY" in audit_table or "POCHYBNÁ FAKTA" in audit_table)
        if not has_work:
            return ProcessingResult(
                success=True, content=article_content,
                tokens_used=audit_result.tokens_used,
                input_tokens=audit_result.input_tokens,
                output_tokens=audit_result.output_tokens,
            )

        # Call 2: Verify → PATCH bloky
        patch_result = self._verify_and_apply(article_content, audit_table)
        if not patch_result.success:
            logger.warning("Verify selhal — fallback na původní text")
            return ProcessingResult(
                success=True, content=article_content,
                tokens_used=(audit_result.tokens_used or 0) + (patch_result.tokens_used or 0),
                input_tokens=(audit_result.input_tokens or 0) + (patch_result.input_tokens or 0),
                output_tokens=(audit_result.output_tokens or 0) + (patch_result.output_tokens or 0),
            )

        # Deterministická aplikace PATCH bloků na originální text
        raw_patches = patch_result.content
        if "### NO PATCHES" in raw_patches or "### PATCH" not in raw_patches:
            # Žádné opravy — vrať originál
            logger.info("Phase 4: žádné PATCH bloky — text beze změn")
            patched_text = article_content
            patch_report = []
        else:
            patched_text, patch_report = self._apply_patches(article_content, raw_patches)
            applied_count = sum(1 for p in patch_report if "applied" in p.get("status", ""))
            skipped_count = sum(1 for p in patch_report if p.get("status") == "skipped")
            logger.info("Phase 4 PATCH: %d applied, %d skipped", applied_count, skipped_count)

        total_tokens = (audit_result.tokens_used or 0) + (patch_result.tokens_used or 0)
        total_input = (audit_result.input_tokens or 0) + (patch_result.input_tokens or 0)
        total_output = (audit_result.output_tokens or 0) + (patch_result.output_tokens or 0)
        all_searches = (audit_result.web_searches or []) + (patch_result.web_searches or [])

        return ProcessingResult(
            success=True, content=patched_text,
            tokens_used=total_tokens, input_tokens=total_input,
            output_tokens=total_output, truncated=patch_result.truncated,
            web_searches=all_searches,
            artifacts={
                "audit_table": audit_table,
                "raw_patches": raw_patches,
                "patch_report": patch_report,
            }
        )


# ============================================================
# Phase 5: Jazyk a kontext
# ============================================================

class LanguageContextOptimizer(ClaudeProcessor):
    """Komplexní jazyková kontrola — false friends, anglicismy, typografie."""

    DEFAULT_MODEL = MODEL_SONNET
    EFFORT = "medium"
    DISABLE_THINKING = True
    MAX_TOKENS = 32000

    def _load_knowledge_base(self, projects_dir: Path) -> str:
        """Načte knowledge base soubory z _knowledge_base/ podsložky."""
        kb_dir = projects_dir / "_knowledge_base"
        if not kb_dir.exists():
            return ""

        kb_files = [
            ("TRANSLATION_TRAPS.md", "Překladové pasti (false friends)"),
            ("ANGLICISMS_AND_CALQUES.md", "Anglicismy a syntaktické kalky"),
            ("IDIOMS_DATABASE.md", "Idiomy a frazémy"),
            ("COLLOCATIONS_GUIDE.md", "České kolokace"),
            ("TEMPORAL_TERMINOLOGY.md", "Terminologie epoch a období"),
            ("TERMINOLOGY_ACCESSIBILITY.md", "Srozumitelnost terminologie"),
            ("TRANSLITERATION_RULES.md", "Pravidla transliterace"),
        ]

        parts = []
        for filename, header in kb_files:
            filepath = kb_dir / filename
            if not filepath.exists():
                continue
            try:
                content = filepath.read_text(encoding='utf-8')
                parts.append(f"## {header}\n\n{content}")
            except Exception:
                pass

        if not parts:
            return ""
        return "\n\n---\n\n# KNOWLEDGE BASE\n\n" + "\n\n---\n\n".join(parts)

    def check_language_and_context(self, article_content: str) -> ProcessingResult:
        """Provede komplexní jazykovou kontrolu.

        Používá PATCH formát — model vrací jen opravy, ne celý text.
        """
        projects_dir = PROMPTS_DIR / "5-JAZYK-KONTEXT"
        knowledge_base = self._load_knowledge_base(projects_dir)

        corrector_rules = format_corrector_rules_for_prompt(max_per_category=25)
        if corrector_rules:
            knowledge_base = (knowledge_base or "") + corrector_rules

        instruction = f"""TVÝM ÚKOLEM JE PROVÉST KOMPLEXNÍ JAZYKOVOU KONTROLU A VRÁTIT OPRAVY VE FORMÁTU PATCH.

⚠️ NEREPRODUKUJ CELÝ TEXT! Vrať JEN opravy v PATCH formátu.

TEXT K KONTROLE:
{article_content}

---

KATEGORIE KONTROL (všechny povinné):

1. PŘEKLADOVÉ PASTI (False Friends)
   - "ancient" u pravěkých nálezů → "pravěký" (NE starověký)
   - "sensitive" → citlivý (NE senzitivní)
   - "eventually" → nakonec (NE eventuálně)
   - "billion" → miliarda (NE bilion)

2. ANGLICISMY A KALKY
   - implementovat → zavést; fokusovat se → soustředit se
   - Nadměrné pasivum, nominalizace, rozvité přívlastky

3. GRAMATIKA A PRAVOPIS

4. TYPOGRAFIE (POVINNÁ)
   - "text" → „text"; - → – (v rozsazích); 1.1.2026 → 1. 1. 2026
   - 1000000 → 1 000 000; 50% → 50 %; 5km → 5 km

5. OPAKOVÁNÍ SLOV
   - Min. 70% výskytů "říká" nahradit variantami

6. IDIOMY, KOLOKACE, REGISTR

7. STROJOVÝ JAZYK — odstranit generické fráze

8. LOGICKÁ KONZISTENCE

VÝSTUPNÍ FORMÁT (PATCH bloky):

Pokud je text bez chyb, vrať:
ŽÁDNÉ OPRAVY

Pokud jsou potřeba opravy:

### PATCH 1:
REPLACE: [přesný existující text k nahrazení — min. 15 znaků]
WITH:
[opravený text]
END_PATCH

### PATCH 2:
REPLACE: [další text k nahrazení]
WITH:
[opravený text]
END_PATCH

## JAZYKOVÉ A KONTEXTOVÉ OPRAVY
- [kategorie]: [co bylo opraveno]

PRAVIDLA:
- REPLACE musí být PŘESNÁ kopie textu z článku (case-sensitive)
- Používej dostatečně dlouhé kotvy pro jednoznačnou identifikaci
- NIKDY neměň <!--[elem-...]--> značky — jsou neviditelné pro tebe
- Každá oprava = jeden PATCH blok
{knowledge_base}"""

        result = self.process_with_project(
            content="", project_dir=projects_dir,
            additional_instruction=instruction
        )

        # Aplikuj PATCH bloky na originální text
        if result.success and result.content:
            if "ŽÁDNÉ OPRAVY" in result.content:
                result.content = article_content + "\n\n---\n\n## JAZYKOVÉ A KONTEXTOVÉ OPRAVY\n- Text je v pořádku, žádné opravy."
            elif "### PATCH" in result.content:
                result.content = _apply_patches(article_content, result.content, "JAZYKOVÉ A KONTEXTOVÉ OPRAVY")
            # else: neočekávaný formát — ponechat raw output

        return result


# ============================================================
# Phase 6: Stylistika
# ============================================================

class StylisticEditor(ClaudeProcessor):
    """Stylistická kontrola — plynulost, rytmus, opakování slov."""

    _PHASE6_MODEL = os.environ.get("PHASE6_MODEL", "").lower()
    DEFAULT_MODEL = MODEL_SONNET if _PHASE6_MODEL == "sonnet" else MODEL_OPUS
    DISABLE_THINKING = True
    MAX_TOKENS = 32000

    def check_style(self, article_content: str) -> ProcessingResult:
        """Provede stylistickou kontrolu.

        Používá PATCH formát — model vrací jen opravy, ne celý text.
        """
        instruction = f"""TVÝM ÚKOLEM JE VYLEPŠIT STYLISTIKU A VRÁTIT OPRAVY VE FORMÁTU PATCH.

⚠️ NEREPRODUKUJ CELÝ TEXT! Vrať JEN opravy v PATCH formátu.

TEXT K KONTROLE:
{article_content}

---

KONTROLUJ: plynulost, rytmus, slovní zásobu, opakování slov, kohezi odstavců

VÝSTUPNÍ FORMÁT (PATCH bloky):

Pokud je text stylisticky v pořádku, vrať:
ŽÁDNÉ OPRAVY

Pokud jsou potřeba opravy:

### PATCH 1:
REPLACE: [přesný existující text k nahrazení — min. 15 znaků]
WITH:
[stylisticky vylepšený text]
END_PATCH

## STYLISTICKÉ ÚPRAVY
- [co bylo změněno a proč]

PRAVIDLA:
- REPLACE musí být PŘESNÁ kopie textu z článku (case-sensitive)
- Používej dostatečně dlouhé kotvy pro jednoznačnou identifikaci
- NIKDY neměň <!--[elem-...]--> značky — jsou neviditelné pro tebe
- Zachovej autorský styl a význam — jen vylepšuj, neměň smysl"""

        projects_dir = PROMPTS_DIR / "7-STYLISTIKA"
        result = self.process_with_project(
            content="", project_dir=projects_dir,
            additional_instruction=instruction
        )

        # Aplikuj PATCH bloky na originální text
        if result.success and result.content:
            if "ŽÁDNÉ OPRAVY" in result.content:
                result.content = article_content + "\n\n---\n\n## STYLISTICKÉ ÚPRAVY\n- Text je stylisticky v pořádku."
            elif "### PATCH" in result.content:
                result.content = _apply_patches(article_content, result.content, "STYLISTICKÉ ÚPRAVY")

        return result
