"""Text pipeline orchestrator — runs phases 2-6 on translated IDML elements.

Usage:
    pipeline = TextPipeline(config=PipelineConfig(phases=[2, 3, 4, 5, 6]))
    result = pipeline.run(project)
"""

import time
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from .element_merger import ElementMerger
from .phases import (
    CompletenessChecker,
    TermVerifier,
    FactChecker,
    LanguageContextOptimizer,
    StylisticEditor,
    format_termdb_for_prompt,
    detect_domains_from_text,
)
from .findings_ledger import (
    load_findings_ledger,
    update_findings_ledger,
    format_findings_for_phase,
)
from .processor import ProcessingResult

# CzechCorrector — phase 4.5
try:
    from ngm_terminology.corrector import CzechCorrector
    _CORRECTOR_AVAILABLE = True
except ImportError:
    _CORRECTOR_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Konfigurace pipeline."""
    phases: list = field(default_factory=lambda: [2, 3, 4, 5, 6])
    api_key: Optional[str] = None
    # Phase 6 model override: "sonnet" pro levnější variantu
    phase6_model: Optional[str] = None


@dataclass
class PhaseResult:
    """Výsledek jedné fáze."""
    phase: int
    phase_name: str
    success: bool
    duration_s: float = 0
    tokens_used: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    web_searches: int = 0
    elements_updated: int = 0
    error: Optional[str] = None


@dataclass
class PipelineResult:
    """Celkový výsledek pipeline."""
    success: bool
    phases_completed: list = field(default_factory=list)
    phases_failed: list = field(default_factory=list)
    total_tokens: int = 0
    total_duration_s: float = 0
    elements_updated: int = 0
    error: Optional[str] = None

    @property
    def phase_results(self) -> list:
        return self.phases_completed + self.phases_failed


PHASE_NAMES = {
    2: "Kontrola úplnosti",
    3: "Ověření termínů",
    4: "Kontrola faktů",
    45: "CzechCorrector",
    5: "Jazyk a kontext",
    6: "Stylistika",
}


class TextPipeline:
    """Orchestrátor textového pipeline — fáze 2-6."""

    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig()

    def run(self, project, progress_callback=None) -> PipelineResult:
        """Spustí pipeline na projektu.

        Args:
            project: Project objekt s elements[]
            progress_callback: callback(phase, phase_name, status, extra=None)
                status: "running" | "done" | "failed"
                extra: dict s duration_s, tokens, error...

        Returns:
            PipelineResult
        """
        start_time = time.time()
        result = PipelineResult(success=True)

        # Ověření — musí být přeložené elementy
        processable = ElementMerger.count_processable(project.elements)
        if processable == 0:
            return PipelineResult(
                success=False,
                error="Žádné přeložené elementy k zpracování"
            )

        logger.info(f"Pipeline start: {processable} elementů, fáze {self.config.phases}")

        # Spojit elementy do jednoho textu
        merged_text = ElementMerger.merge(project.elements)
        original_text = ElementMerger.merge_original(project.elements)

        # Project dir pro findings ledger
        from config import PROJECTS_DIR
        project_dir = PROJECTS_DIR / project.id
        project_dir.mkdir(parents=True, exist_ok=True)

        # Spustit fáze sekvenčně
        current_text = merged_text

        for phase in self.config.phases:
            phase_name = PHASE_NAMES.get(phase, f"Fáze {phase}")

            if progress_callback:
                progress_callback(phase, phase_name, "running")

            logger.info(f"=== Phase {phase}: {phase_name} ===")
            phase_start = time.time()

            try:
                phase_result = self._run_phase(
                    phase, current_text, original_text,
                    project_dir, project
                )

                duration = time.time() - phase_start
                pr = PhaseResult(
                    phase=phase,
                    phase_name=phase_name,
                    success=phase_result.success,
                    duration_s=round(duration, 1),
                    tokens_used=phase_result.tokens_used,
                    input_tokens=phase_result.input_tokens,
                    output_tokens=phase_result.output_tokens,
                    web_searches=len(phase_result.web_searches),
                )

                if phase_result.success and phase_result.content:
                    # Aktualizuj text pro další fázi
                    current_text = phase_result.content

                    # Aktualizuj findings ledger
                    update_findings_ledger(project_dir, phase, phase_result.content)

                    result.phases_completed.append(pr)
                    result.total_tokens += phase_result.tokens_used
                    logger.info(
                        f"Phase {phase} OK: {duration:.1f}s, "
                        f"{phase_result.tokens_used} tokens"
                    )
                else:
                    pr.error = phase_result.error
                    result.phases_failed.append(pr)
                    logger.warning(f"Phase {phase} FAILED: {phase_result.error}")

                if progress_callback:
                    status = "done" if phase_result.success else "failed"
                    progress_callback(phase, phase_name, status, {
                        "duration_s": pr.duration_s,
                        "tokens": pr.tokens_used,
                        "success": pr.success,
                        "error": pr.error,
                    })

            except Exception as e:
                duration = time.time() - phase_start
                pr = PhaseResult(
                    phase=phase, phase_name=phase_name,
                    success=False, duration_s=round(duration, 1),
                    error=str(e)
                )
                result.phases_failed.append(pr)
                logger.error(f"Phase {phase} EXCEPTION: {e}")

                if progress_callback:
                    progress_callback(phase, phase_name, "failed", {
                        "duration_s": pr.duration_s,
                        "error": str(e),
                    })

        # Phase 4.5: CzechCorrector (deterministický, běží vždy)
        if _CORRECTOR_AVAILABLE:
            try:
                corrector = CzechCorrector()
                corrector_result = corrector.correct(
                    current_text,
                    fix_typography=True,
                    check_spelling=False,
                    check_rules=False,
                )
                if corrector_result.auto_count > 0:
                    current_text = corrector_result.text
                    logger.info(f"Phase 4.5 CzechCorrector: {corrector_result.auto_count} oprav")
                corrector.close()
            except Exception as e:
                logger.warning(f"CzechCorrector: {e}")

        # Rozdělit zpět na elementy
        updated_texts = ElementMerger.split_back(current_text, project.elements)

        # Aplikovat na projekt
        updated_count = 0
        for elem in project.elements:
            if elem.id in updated_texts:
                new_text = updated_texts[elem.id]
                if new_text != elem.czech:
                    elem.czech = new_text
                    updated_count += 1

        result.elements_updated = updated_count
        result.total_duration_s = round(time.time() - start_time, 1)

        if result.phases_failed and not result.phases_completed:
            result.success = False
            result.error = "Všechny fáze selhaly"

        logger.info(
            f"Pipeline done: {len(result.phases_completed)} OK, "
            f"{len(result.phases_failed)} failed, "
            f"{updated_count} elementů aktualizováno, "
            f"{result.total_tokens} tokenů, {result.total_duration_s}s"
        )

        return result

    def _run_phase(
        self, phase: int, current_text: str, original_text: str,
        project_dir: Path, project
    ) -> ProcessingResult:
        """Spustí jednu fázi pipeline."""
        api_key = self.config.api_key

        # Findings ledger context
        ledger = load_findings_ledger(project_dir)
        findings_ctx = format_findings_for_phase(ledger, phase)
        if findings_ctx:
            text_with_ctx = findings_ctx + current_text
        else:
            text_with_ctx = current_text

        if phase == 2:
            checker = CompletenessChecker(api_key=api_key)
            return checker.check_completeness(original_text, text_with_ctx)

        elif phase == 3:
            verifier = TermVerifier(api_key=api_key)
            # Build TermDB context
            domains = detect_domains_from_text(current_text)
            termdb_ctx = format_termdb_for_prompt(
                max_terms=100, article_domains=domains
            )
            return verifier.verify_terms(text_with_ctx, termdb_ctx)

        elif phase == 4:
            checker = FactChecker(api_key=api_key)
            return checker.check_facts(text_with_ctx)

        elif phase == 5:
            optimizer = LanguageContextOptimizer(api_key=api_key)
            return optimizer.check_language_and_context(text_with_ctx)

        elif phase == 6:
            editor = StylisticEditor(api_key=api_key)
            return editor.check_style(text_with_ctx)

        else:
            return ProcessingResult(
                success=False, content="",
                error=f"Neznámá fáze: {phase}"
            )
