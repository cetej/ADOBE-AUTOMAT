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

# --- Terminologické utility ---

# Graceful import ngm-terminology — JEDINÝ ZDROJ: termdb.db (246K+ termínů)
try:
    from ngm_terminology import NormalizedTermDB
    _main_db = None

    _main_db_path = Path(r"C:\Users\stock\Documents\000_NGM\BIOLIB\termdb.db")
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
        instruction = """TVÝM ÚKOLEM JE ZKONTROLOVAT A OPRAVIT PŘEKLAD.

⚠️ KRITICKÉ:
- NIKDY NEZKRACUJ TEXT! Výstup MUSÍ obsahovat CELÝ překlad od začátku do konce.
- ZACHOVEJ VŠECHNY HTML značky <!--[elem-...]-->...<!--[/elem-...]-->  beze změny!
  Tyto značky slouží k identifikaci textových bloků a NESMÍ být odstraněny ani změněny.

POSTUP:
1. Porovnej originál s překladem — identifikuj VŠECHNY chybějící části
2. Pro každou chybějící část:
   - Přelož ji do češtiny
   - Vlož ji na správné místo v překladu (do příslušného <!--[elem-...]--> bloku)
3. Zkontroluj, že jsou přeloženy VŠECHNY popisky

VÝSTUP:
1. KOMPLETNÍ OPRAVENÝ PŘEKLAD se všemi <!--[elem-...]--> značkami
2. Na konci sekce ## PROVEDENÉ DOPLNĚNÍ se seznamem doplněných částí

PRAVIDLA:
- Text musí mít STEJNOU nebo VĚTŠÍ délku než vstupní překlad
- Zachovej VŠECHNY sekce a odstavce
- NIKDY nevracej jen analýzu — VŽDY vrať KOMPLETNÍ opravený text"""

        projects_dir = PROMPTS_DIR / "2-KONTROLA_UPLNOSTI_PREKLADU"
        return self.process_with_project(
            content=content,
            project_dir=projects_dir,
            additional_instruction=instruction
        )


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

    @staticmethod
    def _local_lookup(text: str) -> tuple[str, list[dict]]:
        """Vyhledá termíny v lokálních DB — vrací kontext a seznam nalezených."""
        found = []
        # Extrahuj unikátní slova/fráze z textu (bez HTML značek)
        import re
        clean = re.sub(r'<!--\[.*?\]-->', '', text)

        if _multi_db:
            try:
                # Hledej anglické termíny ve zdrojovém textu
                words = set()
                for match in re.finditer(r'[A-Z][a-z]+(?:\s+[A-Z]?[a-z]+)*', clean):
                    words.add(match.group())
                for match in re.finditer(r'[A-Z]{2,}', clean):
                    words.add(match.group())

                for word in words:
                    if len(word) < 3:
                        continue
                    try:
                        results = _multi_db.lookup(word)
                        if results:
                            for r in results[:1]:  # první match
                                found.append({
                                    "en": word,
                                    "cz": r.get("cz", r.get("czech", "")),
                                    "source": "termdb",
                                })
                    except Exception:
                        pass
            except Exception:
                pass

        if _species_db:
            try:
                for match in re.finditer(r'[A-Z][a-z]+(?:\s+[a-z]+)?', clean):
                    word = match.group()
                    if len(word) < 4:
                        continue
                    try:
                        result = _species_db.lookup(word)
                        if result:
                            found.append({
                                "en": word,
                                "cz": result.get("cz", result.get("czech_name", "")),
                                "lat": result.get("latin", word),
                                "source": "species_db",
                            })
                    except Exception:
                        pass
            except Exception:
                pass

        if _term_db:
            try:
                conn = _term_db._conn()
                c = conn.cursor()
                for match in re.finditer(r'[A-Za-z][a-z]+(?:\s+[A-Za-z][a-z]+)*', clean):
                    word = match.group()
                    if len(word) < 3:
                        continue
                    c.execute("SELECT en, cz, lat FROM terms WHERE LOWER(en) = LOWER(?) LIMIT 1", (word,))
                    row = c.fetchone()
                    if row:
                        found.append({
                            "en": row["en"],
                            "cz": row["cz"],
                            "lat": row["lat"] or "",
                            "source": "terminology_db",
                        })
                conn.close()
            except Exception:
                pass

        # Deduplicate by EN
        seen = set()
        unique = []
        for f in found:
            key = f["en"].lower()
            if key not in seen:
                seen.add(key)
                unique.append(f)

        if unique:
            lines = [
                "## LOKÁLNĚ OVĚŘENÉ TERMÍNY (z databáze — NEOVĚŘUJ web searchem)",
                "", "| EN | CZ | Latin | Zdroj |", "|---|---|---|---|"
            ]
            for f in unique:
                lines.append(f"| {f['en']} | {f['cz']} | {f.get('lat', '—')} | {f['source']} |")
            lines.append("")
            context = "\n".join(lines)
        else:
            context = ""

        logger.info(f"[Phase 3] Lokální DB lookup: {len(unique)} termínů nalezeno")
        return context, unique

    def _research_terms(self, translated_content: str, termdb_context: str = "",
                         local_found: list = None) -> ProcessingResult:
        """Call 1 (Research): lokální DB kontext + web search jen pro neznámé."""
        db_block = ""
        if termdb_context:
            db_block = f"""{termdb_context}

---

"""
        local_block = ""
        if local_found:
            local_block = f"""## PŘEDEM OVĚŘENÉ TERMÍNY (lokální DB — {len(local_found)} termínů)
Tyto termíny jsou OVĚŘENÉ z lokální databáze. NEPOUŽÍVEJ na ně web search.
Soustřeď web search JEN na termíny, které NEJSOU v lokální DB.

"""

        instruction = f"""TVÝM ÚKOLEM JE IDENTIFIKOVAT A OVĚŘIT ODBORNÉ TERMÍNY V TEXTU.

{db_block}{local_block}TEXT K ANALÝZE:
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

        # Research config: thinking ON, medium effort
        saved = (self.DISABLE_THINKING, self.EFFORT, self.MAX_TOKENS)
        try:
            self.DISABLE_THINKING = False
            self.EFFORT = "medium"
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
        """Ověří termíny (Lokální DB → Research → Apply)."""
        # Krok 0: Lokální DB lookup — okamžitý, bez API volání
        local_context, local_found = self._local_lookup(translated_content)

        # Call 1: Research — web search jen pro neznámé termíny
        full_context = (local_context + "\n\n" + termdb_context).strip() if local_context else termdb_context
        research_result = self._research_terms(
            translated_content, full_context, local_found=local_found
        )
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
            self.EFFORT = "medium"
            self.MAX_TOKENS = 16000
            logger.info("[Phase 4 Call 1/2] Audit: reasoning bez tools")
            return self.process_with_project(
                content="", project_dir=projects_dir,
                additional_instruction=instruction
            )
        finally:
            self.DISABLE_THINKING, self.EFFORT, self.MAX_TOKENS = saved

    def _verify_and_apply(self, article_content: str, audit_table: str) -> ProcessingResult:
        """Call 2 (Verify & Apply): web search + aplikace oprav."""
        instruction = f"""TVÝM ÚKOLEM JE OVĚŘIT POCHYBNÁ FAKTA A APLIKOVAT OPRAVY.

## AUDIT:
{audit_table}

---

## TEXT K OPRAVĚ:
{article_content}

---

## INSTRUKCE:
1. Ověř pochybná fakta web searchem
2. Aplikuj VŠECHNY převody jednotek z tabulky
3. Aplikuj ověřené faktické opravy
4. ZACHOVEJ VŠECHNY <!--[elem-...]--> značky!
5. NIKDY nezkracuj text

## VÝSTUP:
1. KOMPLETNÍ TEXT s opravami
2. Na konci:
## FAKTICKÉ OPRAVY
| # | Typ | Původní text | Oprava | Důvod | Zdroj |
|---|---|---|---|---|---|"""

        verify_tools = [
            {"type": "web_search_20260209", "name": "web_search", "max_uses": self.FACT_SEARCH_MAX_USES}
        ]

        # Adaptivní MAX_TOKENS
        saved_max = self.MAX_TOKENS
        if len(article_content) > 20000:
            self.MAX_TOKENS = 48000

        try:
            logger.info("[Phase 4 Call 2/2] Verify & Apply: web search + reprodukce")
            return self.process(
                content=instruction,
                system_prompt="Jsi faktický korektor. Ověřuješ fakta web searchem a aplikuješ opravy. ZACHOVEJ <!--[elem-...]--> značky. NIKDY nezkracuj text.",
                tools=verify_tools
            )
        finally:
            self.MAX_TOKENS = saved_max

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

        # Call 2: Verify & Apply
        apply_result = self._verify_and_apply(article_content, audit_table)
        if not apply_result.success:
            logger.warning(f"Verify & Apply selhal — fallback na původní text")
            return ProcessingResult(
                success=True, content=article_content,
                tokens_used=(audit_result.tokens_used or 0) + (apply_result.tokens_used or 0),
                input_tokens=(audit_result.input_tokens or 0) + (apply_result.input_tokens or 0),
                output_tokens=(audit_result.output_tokens or 0) + (apply_result.output_tokens or 0),
            )

        # Fragment check
        if len(apply_result.content) < len(article_content) * 0.5:
            logger.warning("Apply vrátil fragment — fallback")
            return ProcessingResult(
                success=True, content=article_content,
                tokens_used=(audit_result.tokens_used or 0) + (apply_result.tokens_used or 0),
                input_tokens=(audit_result.input_tokens or 0) + (apply_result.input_tokens or 0),
                output_tokens=(audit_result.output_tokens or 0) + (apply_result.output_tokens or 0),
            )

        total_tokens = (audit_result.tokens_used or 0) + (apply_result.tokens_used or 0)
        total_input = (audit_result.input_tokens or 0) + (apply_result.input_tokens or 0)
        total_output = (audit_result.output_tokens or 0) + (apply_result.output_tokens or 0)
        all_searches = (audit_result.web_searches or []) + (apply_result.web_searches or [])

        return ProcessingResult(
            success=True, content=apply_result.content,
            tokens_used=total_tokens, input_tokens=total_input,
            output_tokens=total_output, truncated=apply_result.truncated,
            web_searches=all_searches,
            artifacts={"audit_table": audit_table}
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
        """Provede komplexní jazykovou kontrolu."""
        projects_dir = PROMPTS_DIR / "5-JAZYK-KONTEXT"
        knowledge_base = self._load_knowledge_base(projects_dir)

        corrector_rules = format_corrector_rules_for_prompt(max_per_category=25)
        if corrector_rules:
            knowledge_base = (knowledge_base or "") + corrector_rules

        instruction = f"""TVÝM ÚKOLEM JE PROVÉST KOMPLEXNÍ JAZYKOVOU KONTROLU A OPRAVIT NALEZENÉ CHYBY.

⚠️ KRITICKÉ:
- NIKDY NEZKRACUJ TEXT!
- ZACHOVEJ VŠECHNY <!--[elem-...]--> značky beze změny!

TEXT K OPRAVĚ:
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

VÝSTUP:
1. KOMPLETNÍ TEXT s opravami (se všemi <!--[elem-...]--> značkami)
2. Na konci ## JAZYKOVÉ A KONTEXTOVÉ OPRAVY se seznamem změn

NIKDY nevracej jen analýzu — VŽDY vrať KOMPLETNÍ text.
{knowledge_base}"""

        return self.process_with_project(
            content="", project_dir=projects_dir,
            additional_instruction=instruction
        )


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
        """Provede stylistickou kontrolu."""
        instruction = f"""TVÝM ÚKOLEM JE VYLEPŠIT STYLISTIKU A VRÁTIT OPRAVENÝ TEXT.

⚠️ KRITICKÉ:
- NIKDY NEZKRACUJ TEXT!
- ZACHOVEJ VŠECHNY <!--[elem-...]--> značky beze změny!

TEXT K OPRAVĚ:
{article_content}

---

POSTUP:
1. Zkontroluj: plynulost, rytmus, slovní zásobu, opakování slov, kohezi odstavců
2. Oprav PŘÍMO V TEXTU
3. Zachovej CELOU strukturu

VÝSTUP:
1. KOMPLETNÍ TEXT s vylepšenou stylistikou
2. Na konci ## STYLISTICKÉ ÚPRAVY se seznamem změn

PRAVIDLA:
- Zachovej VŠECHNY <!--[elem-...]--> značky na jejich místech
- Délka výstupu STEJNÁ nebo VĚTŠÍ než vstup
- Zachovej autorský styl a význam

NIKDY nevracej jen analýzu — VŽDY vrať KOMPLETNÍ text."""

        projects_dir = PROMPTS_DIR / "7-STYLISTIKA"
        return self.process_with_project(
            content="", project_dir=projects_dir,
            additional_instruction=instruction
        )
