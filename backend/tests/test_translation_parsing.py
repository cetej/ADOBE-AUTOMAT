"""Regression testy pro parsovani Claude API odpovedi v translation_service.

Pokryva tri bug scenare nalezene 2026-04-29 pri prekladu mapy Alaska_v16:
  1. Raw control chars (LF/CR/TAB) UVNITR JSON stringu (Claude vraci preklad
     viceradkoveho vstupu se stejnymi raw newlines, RFC 8259 to zakazuje).
  2. Blanket re.sub by escapnul i strukturalni whitespace mezi JSON tokens
     (regression check — drzi parser-aware semantiku).
  3. Halucinace klice — Claude vraci "text"/"translation"/"cs" misto "czech"
     (kopiruje vstupni klic). Tolerant mapping by mel zachytit.

Spusteni:
    cd backend
    python -m tests.test_translation_parsing

Nezavisi na pytestu, jen standalone Python (assert).
"""

import sys
import json
import os
from pathlib import Path

# Pridat backend/ do sys.path aby fungovaly importy "from services...."
_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
sys.path.insert(0, str(_BACKEND))

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from services.translation_service import (
    _escape_control_chars_in_strings,
    _fix_unescaped_quotes,
    _strip_cyrillic_homoglyphs,
)


# === Bug 1: raw control chars uvnitr JSON stringu ===

def test_lf_inside_string_escaped():
    """Claude vrati preklad s raw LF uvnitr stringu — escapovat na \\u000a."""
    case = '[{"czech": "Smer\npohledu"}]'
    out = _escape_control_chars_in_strings(case)
    assert out != case, "LF v stringu mel byt escapovan"
    parsed = json.loads(out)
    assert parsed == [{"czech": "Smer\npohledu"}], f"Got {parsed!r}"


def test_cr_inside_string_escaped():
    """Stejny mechanismus pro CR (Illustrator format)."""
    case = '[{"czech": "Smer\rpohledu"}]'
    out = _escape_control_chars_in_strings(case)
    parsed = json.loads(out)
    assert parsed == [{"czech": "Smer\rpohledu"}]


def test_tab_inside_string_escaped():
    case = '[{"czech": "Smer\tpohledu"}]'
    out = _escape_control_chars_in_strings(case)
    parsed = json.loads(out)
    assert parsed == [{"czech": "Smer\tpohledu"}]


# === Bug 2: parser-aware semantika — whitespace mezi tokens nemenit ===

def test_whitespace_between_tokens_preserved():
    """Raw LF mezi JSON tokens je legitimni whitespace — neescapovat.

    Pri blanket re.sub(r'[\\x00-\\x1f]', ...) by se stalo:
        [\\u000a  {\\u000a  "id" — toto NENI platny JSON.
    """
    case = '[\n  {\n    "id": "x"\n  }\n]'
    out = _escape_control_chars_in_strings(case)
    assert out == case, f"Whitespace mezi tokens byl modifikovan:\n  in:  {case!r}\n  out: {out!r}"
    parsed = json.loads(out)
    assert parsed == [{"id": "x"}]


def test_whitespace_and_string_combined():
    """Kombinace: raw LF mezi tokens (zachovat) + raw LF v stringu (escapovat)."""
    case = '[\n  {"czech": "Smer\npohledu"},\n  {"czech": "Test\rdva"}\n]'
    out = _escape_control_chars_in_strings(case)
    parsed = json.loads(out)
    assert parsed[0]["czech"] == "Smer\npohledu"
    assert parsed[1]["czech"] == "Test\rdva"


# === Edge cases pro escape semantiku ===

def test_escape_sequence_preserved():
    """Backslash-escape v stringu (\\\") nesmi byt rozbit."""
    case = '[{"czech": "a\\"b"}]'
    out = _escape_control_chars_in_strings(case)
    parsed = json.loads(out)
    assert parsed == [{"czech": 'a"b'}], f"Got {parsed!r}"


def test_unicode_escape_preserved():
    """Existujici \\uXXXX sekvence v stringu nesmi byt rozbita."""
    case = '[{"czech": "Praha\\u2014mesto"}]'
    out = _escape_control_chars_in_strings(case)
    parsed = json.loads(out)
    assert parsed == [{"czech": "Praha—mesto"}]


def test_empty_input():
    assert _escape_control_chars_in_strings("") == ""


def test_no_strings_no_change():
    """JSON bez stringu (jen array) — pass-through."""
    case = '[1, 2, 3]'
    out = _escape_control_chars_in_strings(case)
    assert out == case
    assert json.loads(out) == [1, 2, 3]


# === Bug 3 regression: tolerant mapping logic ===

def test_tolerant_mapping_czech_present():
    """Standard pripad — Claude vrati 'czech', tolerant mapping ho preferuje."""
    r = {"id": "x", "czech": "Smer", "text": "should-not-be-used"}
    val = r.get("czech") or r.get("text") or r.get("translation") or r.get("cs")
    assert val == "Smer"


def test_tolerant_mapping_text_fallback():
    """Halucinace: Claude vrati 'text' misto 'czech'."""
    r = {"id": "x", "text": "Smer"}
    val = r.get("czech") or r.get("text") or r.get("translation") or r.get("cs")
    assert val == "Smer"


def test_tolerant_mapping_translation_fallback():
    r = {"id": "x", "translation": "Smer"}
    val = r.get("czech") or r.get("text") or r.get("translation") or r.get("cs")
    assert val == "Smer"


def test_tolerant_mapping_cs_fallback():
    r = {"id": "x", "cs": "Smer"}
    val = r.get("czech") or r.get("text") or r.get("translation") or r.get("cs")
    assert val == "Smer"


def test_tolerant_mapping_no_value_returns_none():
    """Zadny znamy klic — fallback chain vrati None."""
    r = {"id": "x", "garbage_key": "Smer"}
    val = r.get("czech") or r.get("text") or r.get("translation") or r.get("cs")
    assert val is None


# === Realny payload z Alaska mapy (regression fixture) ===

def test_alaska_real_payload_subset():
    """Subset 5 elementu z mapy Alaska, ktere obsahuji raw LF v stringu.

    Hodnoty 'czech' replikuji to, co Claude realne vracel. Test overuje, ze
    cely flow (escape control chars → json.loads → tolerant mapping) prochazi.
    """
    raw = (
        '[\n'
        '  {"id": "Globe labels/0", "czech": "Smer\npohledu"},\n'
        '  {"id": "Globe labels/1", "czech": "Severni\nledovy ocean"},\n'
        '  {"id": "Globe labels/2", "czech": "Aljaska\n(USA)"},\n'
        '  {"id": "T-Tsunami outer glow/8", "czech": "Barry Arm\ncas prichodu tsunami:\n20 minut"},\n'
        '  {"id": "Inset Labels/0", "czech": "Victory\nBible Camp"}\n'
        ']'
    )
    # Primary parse selze (raw LF v stringu)
    try:
        json.loads(raw)
        assert False, "Parse mel selhat — fixture neni reprezentativni"
    except json.JSONDecodeError:
        pass

    # Recovery 1 — escape control chars v stringech
    sanitized = _escape_control_chars_in_strings(raw)
    parsed = json.loads(sanitized)
    assert len(parsed) == 5
    assert parsed[0]["czech"] == "Smer\npohledu"
    assert parsed[3]["czech"] == "Barry Arm\ncas prichodu tsunami:\n20 minut"

    # Tolerant mapping — vsechny maji "czech"
    for r in parsed:
        val = r.get("czech") or r.get("text") or r.get("translation") or r.get("cs")
        assert val is not None, f"Zadna hodnota pro {r['id']}"


def test_alaska_real_payload_with_key_hallucination():
    """Hypoteticka regrese: Claude vrati 'text' misto 'czech' (pre-fix v3 chovani).

    Kombinuje bug 1 (raw LF) + bug 3 (spatny klic) — overuje, ze tolerant
    mapping funguje i po recovery 1.
    """
    raw = (
        '[\n'
        '  {"id": "Globe labels/0", "text": "Smer\npohledu"},\n'
        '  {"id": "Globe labels/1", "text": "Severni\nledovy ocean"}\n'
        ']'
    )
    sanitized = _escape_control_chars_in_strings(raw)
    parsed = json.loads(sanitized)
    for r in parsed:
        val = r.get("czech") or r.get("text") or r.get("translation") or r.get("cs")
        assert val is not None
    assert parsed[0]["text"] == "Smer\npohledu"


# === Bug 4 regression: CyrillicGuard (sesuvы -> sesuvy) ===

def test_cyrillic_yeru_replaced():
    """Realny pripad z Alaska mapy: 'sesuvы' (U+044B) -> 'sesuvy' (U+0079)."""
    fixed, n, unmapped = _strip_cyrillic_homoglyphs("Aktivní\nsesuvы")
    assert fixed == "Aktivní\nsesuvy", f"Got {fixed!r}"
    assert n == 1
    assert unmapped == []


def test_cyrillic_lookalikes_replaced():
    """Bezne homoglyphy: cyrilske 'a' (U+0430) v textu vypada jako latinka."""
    # Vyrobime "Praha" se 2 cyrilskymi 'a' uprostred
    case = "Pr" + "а" + "h" + "а"  # Praha s cyrilskymi 'a'
    assert any(0x0400 <= ord(c) <= 0x04FF for c in case), "fixture musi obsahovat cyrilici"
    fixed, n, unmapped = _strip_cyrillic_homoglyphs(case)
    assert fixed == "Praha", f"Got {fixed!r}"
    assert n == 2
    assert unmapped == []
    # Vsechny znaky musi byt latinka po fix
    assert all(ord(c) < 0x0400 for c in fixed)


def test_cyrillic_no_op_for_pure_latin():
    """Cisty latinkovy text — zadne zmeny."""
    case = "Severní ledový oceán — Aljaška (USA)"
    fixed, n, unmapped = _strip_cyrillic_homoglyphs(case)
    assert fixed == case
    assert n == 0
    assert unmapped == []


def test_cyrillic_unmapped_preserved():
    """Cyrilice bez mappingu (napr. 'б', 'ж', 'ш') — necha, hlasi unmapped."""
    case = "test ж text"  # 'ж' = U+0436, neni v mappingu
    fixed, n, unmapped = _strip_cyrillic_homoglyphs(case)
    assert fixed == case  # zustal nezmeneny
    assert n == 0
    assert unmapped == ["ж"]


def test_cyrillic_empty_input():
    fixed, n, unmapped = _strip_cyrillic_homoglyphs("")
    assert fixed == ""
    assert n == 0
    assert unmapped == []


def test_cyrillic_multi_char_replacement():
    """Vice cyrilskych homoglyphu v jednom retezci."""
    # "соре" — vsechno cyrilice, vypada jako "cope"
    case = "соре"
    fixed, n, unmapped = _strip_cyrillic_homoglyphs(case)
    assert fixed == "cope"
    assert n == 4
    assert unmapped == []


# === Test runner ===

def main():
    tests = [
        (name, obj)
        for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    passed = 0
    failed = []
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {name}: {e}")
            failed.append(name)
        except Exception as e:
            print(f"  ERROR {name}: {type(e).__name__}: {e}")
            failed.append(name)

    print()
    print(f"  {passed}/{len(tests)} passed")
    if failed:
        print(f"  Failed: {', '.join(failed)}")
        sys.exit(1)
    print("  ALL TESTS PASSED")


if __name__ == "__main__":
    main()
