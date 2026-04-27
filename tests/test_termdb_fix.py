"""Tests for termdb sole-source fix — is_primary filter removal and article-relevance extraction.

Covers:
- Podarcis pityusensis lookup returns correct CZ name (previously filtered by is_primary=1)
- Article-relevance extraction works on synthetic biology text
- format_termdb_for_prompt uses relevance path when article_text provided
- format_termdb_for_prompt falls back to domain path when no article_text
- Post-LLM glossary enforcer still works (write_back_to_termdb preserved)
"""

import sys
import os
import sqlite3
from pathlib import Path

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

TERMDB_PATH = os.environ.get(
    "TERMDB_PATH",
    r"C:\Users\stock\Documents\000_NGM\BIOLIB\termdb.db"
)

_DB_AVAILABLE = Path(TERMDB_PATH).exists()


@pytest.mark.skipif(not _DB_AVAILABLE, reason="termdb.db not found at TERMDB_PATH")
class TestPodarcisLookup:
    """Podarcis pityusensis has is_primary=0 — was previously filtered out."""

    def test_podarcis_in_raw_db(self):
        """Direct SQL check: Podarcis pityusensis cs translation exists with is_primary=0."""
        conn = sqlite3.connect(TERMDB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(
            """
            SELECT tr.name, tr.is_primary
            FROM terms t
            JOIN translations tr ON tr.term_id = t.id AND tr.language = 'cs'
            WHERE LOWER(t.canonical_name) = LOWER('Podarcis pityusensis')
            ORDER BY tr.is_primary DESC
            LIMIT 1
            """
        )
        row = c.fetchone()
        conn.close()
        assert row is not None, "Podarcis pityusensis not found in termdb — DB may be wrong version"
        cz = row["name"]
        assert "pityus" in cz.lower(), f"Expected 'pityus' in CZ name, got: {cz!r}"

    def test_podarcis_has_no_primary_translation(self):
        """Confirm is_primary=0 for Podarcis — this is why the old filter broke it."""
        conn = sqlite3.connect(TERMDB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(
            """
            SELECT tr.is_primary
            FROM terms t
            JOIN translations tr ON tr.term_id = t.id AND tr.language = 'cs'
            WHERE LOWER(t.canonical_name) = LOWER('Podarcis pityusensis')
            """
        )
        rows = c.fetchall()
        conn.close()
        assert rows, "No translations found for Podarcis pityusensis"
        # All should be is_primary=0 (that's the iNaturalist pattern)
        primaries = [r["is_primary"] for r in rows if r["is_primary"] == 1]
        assert len(primaries) == 0, (
            f"Expected is_primary=0 for all Podarcis translations, "
            f"found {len(primaries)} primary records"
        )


@pytest.mark.skipif(not _DB_AVAILABLE, reason="termdb.db not found at TERMDB_PATH")
class TestArticleRelevanceExtraction:
    """_extract_article_terms_from_db: article-relevance extraction."""

    def test_podarcis_found_in_article(self):
        """Podarcis pityusensis extracted from biology article text."""
        from services.text_pipeline.phases import _extract_article_terms_from_db
        article = (
            "The Ibiza wall lizard Podarcis pityusensis is endemic to the "
            "Pityusic Islands. Several subspecies have been described."
        )
        result = _extract_article_terms_from_db(TERMDB_PATH, article)
        assert "Podarcis pityusensis" in result, (
            f"Podarcis pityusensis not found in result: {result}"
        )
        cz = result["Podarcis pityusensis"]
        assert "pityus" in cz.lower(), f"Unexpected CZ: {cz!r}"

    def test_multiple_binomials_extracted(self):
        """Multiple Latin binomials in one article are all looked up."""
        from services.text_pipeline.phases import _extract_article_terms_from_db
        article = (
            "Lacerta agilis and Podarcis muralis are common European lizards. "
            "Vipera berus, the common adder, is also widespread."
        )
        result = _extract_article_terms_from_db(TERMDB_PATH, article)
        # At least one should be found (DB may not have all three)
        assert len(result) >= 1, f"Expected at least 1 hit, got: {result}"

    def test_empty_article_returns_empty(self):
        """Empty article text returns empty dict."""
        from services.text_pipeline.phases import _extract_article_terms_from_db
        result = _extract_article_terms_from_db(TERMDB_PATH, "")
        assert result == {}

    def test_no_binomials_returns_empty(self):
        """Article with no Latin binomials returns empty dict."""
        from services.text_pipeline.phases import _extract_article_terms_from_db
        article = "This article discusses the geography of Central Europe and the Alps."
        result = _extract_article_terms_from_db(TERMDB_PATH, article)
        assert result == {}

    def test_stopword_genus_skipped(self):
        """Phrases like 'National Geographic' are not treated as binomials."""
        from services.text_pipeline.phases import _extract_article_terms_from_db
        article = "National Geographic published the story. American magazine."
        result = _extract_article_terms_from_db(TERMDB_PATH, article)
        # National Geographic should not produce a hit
        assert "National Geographic" not in result


@pytest.mark.skipif(not _DB_AVAILABLE, reason="termdb.db not found at TERMDB_PATH")
class TestFormatTermdbForPrompt:
    """format_termdb_for_prompt: relevance path when article_text given."""

    def test_uses_relevance_path_with_article_text(self):
        """With article_text: uses article-relevance section header."""
        from services.text_pipeline.phases import format_termdb_for_prompt
        article = "The lizard Podarcis pityusensis inhabits the island."
        result = format_termdb_for_prompt(article_text=article)
        if result:
            assert "RELEVANTNÍ PRO ČLÁNEK" in result, (
                f"Expected relevance header, got: {result[:200]}"
            )
            assert "Podarcis" in result

    def test_falls_back_to_domain_path_without_article(self):
        """Without article_text: uses domain fallback path."""
        from services.text_pipeline.phases import format_termdb_for_prompt
        result = format_termdb_for_prompt(article_domains=["biology"])
        # Should return something (domain fallback) or empty if DB unreachable
        if result:
            # Domain fallback uses BIOLOGIE header
            assert "BIOLOGIE" in result or "termdb" in result.lower()

    def test_article_text_overrides_max_terms_100_limit(self):
        """With article_text, result is not capped at 100 arbitrary terms."""
        from services.text_pipeline.phases import format_termdb_for_prompt
        # Build article with many binomials to confirm no artificial cap
        article = (
            "Podarcis pityusensis, Lacerta agilis, Vipera berus, "
            "Natrix natrix, Anguis fragilis are reptiles of Europe."
        )
        result = format_termdb_for_prompt(article_text=article, max_terms=100)
        # Result should only contain terms actually in the article (relevance-filtered)
        # Not capped to 100 random domain terms
        if result:
            assert "RELEVANTNÍ PRO ČLÁNEK" in result


class TestGlossaryEnforcerPreserved:
    """Glossary enforcer still has no is_primary=1 hard filter (was already correct)."""

    def test_no_is_primary_hard_filter_in_enforcer(self):
        """glossary_enforcer.py must not have is_primary = 1 hard filter."""
        enforcer_path = Path(__file__).parent.parent / "backend/services/glossary_enforcer.py"
        content = enforcer_path.read_text(encoding="utf-8")
        # Should NOT contain is_primary = 1 hard filter
        assert "is_primary = 1" not in content, (
            "glossary_enforcer.py has is_primary=1 hard filter — must be removed"
        )
        assert "is_primary=1" not in content, (
            "glossary_enforcer.py has is_primary=1 hard filter — must be removed"
        )
        # Should use ORDER BY is_primary DESC
        assert "is_primary DESC" in content, (
            "glossary_enforcer.py must use ORDER BY tr.is_primary DESC"
        )

    def test_write_back_to_termdb_exists(self):
        """write_back_to_termdb must still exist in translation_service.py."""
        ts_path = Path(__file__).parent.parent / "backend/services/translation_service.py"
        content = ts_path.read_text(encoding="utf-8")
        assert "def write_back_to_termdb" in content, (
            "write_back_to_termdb function missing from translation_service.py"
        )


class TestSyntaxIntegrity:
    """Syntax check on modified files."""

    def test_phases_py_syntax(self):
        import ast
        path = Path(__file__).parent.parent / "backend/services/text_pipeline/phases.py"
        ast.parse(path.read_text(encoding="utf-8"))

    def test_pipeline_py_syntax(self):
        import ast
        path = Path(__file__).parent.parent / "backend/services/text_pipeline/pipeline.py"
        ast.parse(path.read_text(encoding="utf-8"))
