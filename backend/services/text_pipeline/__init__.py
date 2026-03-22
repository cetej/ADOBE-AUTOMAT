"""Text pipeline — post-translation processing phases from NG-ROBOT.

Fáze zpracování textu po překladu:
  Phase 2: Kontrola úplnosti překladu
  Phase 3: Ověření termínů (SpeciesDB + TermDB + web search)
  Phase 4: Kontrola faktů + převod jednotek
  Phase 4.5: CzechCorrector (deterministic typography)
  Phase 5: Jazyk a kontext (false friends, anglicismy, gramatika)
  Phase 6: Stylistika
"""

from .pipeline import TextPipeline, PipelineConfig, PipelineResult
from .element_merger import ElementMerger

__all__ = ["TextPipeline", "PipelineConfig", "PipelineResult", "ElementMerger"]
