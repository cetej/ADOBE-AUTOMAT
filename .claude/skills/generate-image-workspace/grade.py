"""Grading script for generate-image skill eval."""
import json, re, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

BASE = Path(__file__).parent / "iteration-1"

def count_words(text):
    """Count words in a prompt block (between ``` markers)."""
    prompts = re.findall(r'```\n(.+?)\n```', text, re.DOTALL)
    return [len(p.split()) for p in prompts]

def grade(result_path, eval_name, is_with_skill):
    text = result_path.read_text(encoding='utf-8')
    expectations = []

    # 1. Three variants
    has_a = bool(re.search(r'Variant[ea]\s*A', text, re.I))
    has_b = bool(re.search(r'Variant[ea]\s*B', text, re.I))
    has_c = bool(re.search(r'Variant[ea]\s*C', text, re.I))
    expectations.append({
        "text": "Three variants (A, B, C)",
        "passed": has_a and has_b and has_c,
        "evidence": f"A={has_a}, B={has_b}, C={has_c}"
    })

    # 2. English prompts
    prompts = re.findall(r'```\n(.+?)\n```', text, re.DOTALL)
    has_english = any(re.search(r'(image|shot|view|light|style|composition|photograph)', p, re.I) for p in prompts)
    expectations.append({
        "text": "Image prompts are in English",
        "passed": has_english,
        "evidence": f"Found {len(prompts)} prompt blocks, English keywords present: {has_english}"
    })

    # 3. Word count 30-50
    word_counts = count_words(text)
    in_range = [30 <= w <= 55 for w in word_counts]  # slight tolerance
    expectations.append({
        "text": "Each prompt is 30-50 words",
        "passed": len(word_counts) >= 3 and all(in_range),
        "evidence": f"Word counts: {word_counts}"
    })

    # 4. Correct aspect ratio
    is_hero = "hero" in eval_name.lower()
    expected_ar = "3:2" if is_hero else "16:9"
    ar_count = text.count(expected_ar)
    expectations.append({
        "text": f"Uses {expected_ar} aspect ratio",
        "passed": ar_count >= 1,
        "evidence": f"Found '{expected_ar}' {ar_count} times"
    })

    # 5. Visual brief used (only for with_skill)
    if is_with_skill:
        has_brief = bool(re.search(r'(vizualni brief|visual.?brief|dominant.?tone|key.?visual|recommended.?style)', text, re.I))
        expectations.append({
            "text": "References visual_brief data",
            "passed": has_brief,
            "evidence": f"Visual brief referenced: {has_brief}"
        })

    # 6. Thumbnail validation (only for with_skill)
    if is_with_skill:
        has_thumb = bool(re.search(r'(thumbnail|100.?67|rozpoznatel|0[.,]5)', text, re.I))
        expectations.append({
            "text": "Performs thumbnail test validation",
            "passed": has_thumb,
            "evidence": f"Thumbnail validation present: {has_thumb}"
        })

    # 7. Asks user choice (only for with_skill)
    if is_with_skill:
        asks = bool(re.search(r'(kter[yý]|A.?/.?B.?/.?C|vybr|zvol)', text, re.I))
        expectations.append({
            "text": "Asks user which variant to generate",
            "passed": asks,
            "evidence": f"User choice prompt: {asks}"
        })

    # 8. Structured variant types (only for with_skill)
    if is_with_skill:
        has_types = bool(re.search(r'(metaforic|editorial|symbolic|symboli)', text, re.I))
        expectations.append({
            "text": "Uses structured variant types (metaphoric/editorial/symbolic)",
            "passed": has_types,
            "evidence": f"Variant types present: {has_types}"
        })

    return {"expectations": expectations}

# Grade all 6 runs
evals = ["fish-cloning-hero", "yellowstone-illustration", "gulf-stream-hero"]
configs = [("with_skill", True), ("without_skill", False)]

summary = {}
for eval_name in evals:
    for config_name, is_ws in configs:
        result_path = BASE / eval_name / config_name / "outputs" / "result.md"
        if not result_path.exists():
            print(f"SKIP {eval_name}/{config_name} — no result.md")
            continue

        grading = grade(result_path, eval_name, is_ws)

        # Save grading.json
        grade_path = BASE / eval_name / config_name / "grading.json"
        grade_path.write_text(json.dumps(grading, indent=2, ensure_ascii=False), encoding='utf-8')

        passed = sum(1 for e in grading["expectations"] if e["passed"])
        total = len(grading["expectations"])
        rate = passed / total if total else 0

        key = f"{eval_name}/{config_name}"
        summary[key] = {"passed": passed, "total": total, "rate": rate}

        status = "PASS" if rate == 1.0 else "PARTIAL" if rate > 0.5 else "FAIL"
        print(f"[{status}] {key}: {passed}/{total} ({rate:.0%})")
        for e in grading["expectations"]:
            icon = "✓" if e["passed"] else "✗"
            print(f"  {icon} {e['text']}: {e['evidence']}")

# Print comparison
print("\n=== COMPARISON ===")
for eval_name in evals:
    ws = summary.get(f"{eval_name}/with_skill", {})
    bl = summary.get(f"{eval_name}/without_skill", {})
    print(f"{eval_name}: with_skill {ws.get('passed',0)}/{ws.get('total',0)} vs baseline {bl.get('passed',0)}/{bl.get('total',0)}")
