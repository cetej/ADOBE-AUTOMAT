---
name: article-status
description: Prehled stavu VSECH zpracovanych clanku v processed/ — kolik je hotovych, rozpracovanych, na ktere fazi stoji. Filtrovani podle data nebo faze, detekce truncation. Pouzij kdyz uzivatel rika "kolik clanku", "stav clanku", "status", "prehled", "co je hotove", "truncation", nebo chce videt tabulku vsech clanku. NEPOUZIVEJ pro diagnostiku jednoho konkretniho clanku.
argument-hint: "[date-prefix | phase-number]"
effort: low
tags: [articles, status, diagnostics]
---

Zobraz stav zpracovani clanku. Spust tento Python skript v Bash:

```bash
cd "C:/Users/stock/Documents/000_NGM/NG-ROBOT" && python -c "
import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

arg = '$ARGUMENTS'.strip()

PHASES = {0:'0_analysis.json', 1:'1_translated.md', 2:'2_completeness.md',
          3:'3_terms.md', 4:'4_facts.md', 5:'5_language.md',
          6:'6_stylized.md', 7:'7_seo.md', 8:'8_related.md', 9:'9_final.md'}
NAMES = {0:'Analyza', 1:'Preklad', 2:'Uplnost', 3:'Terminy', 4:'Fakta',
         5:'Jazyk', 6:'Stylistika', 7:'SEO', 8:'Souvisejici', 9:'Finalni', 10:'Video'}

processed = Path('processed')
if not processed.exists():
    print('Slozka processed/ neexistuje'); sys.exit(1)

filter_phase = int(arg) if arg.isdigit() else None
filter_prefix = arg if arg and not arg.isdigit() else ''

counts = {i: 0 for i in range(-1, 11)}
total = 0
truncated = []

for d in sorted(processed.iterdir(), reverse=True):
    if not d.is_dir() or d.name.startswith('.'): continue
    if filter_prefix and not d.name.startswith(filter_prefix): continue

    phase = -1
    for p in range(9, -1, -1):
        if (d / PHASES[p]).exists():
            phase = p; break

    has_video = (d / 'social').exists() and list((d / 'social').glob('*.mp4'))
    if has_video and phase >= 9: phase = 10

    if filter_phase is not None and phase != filter_phase: continue

    icon = {10: 'OK+V', 9: ' OK ', -1: 'NONE'}.get(phase, f' F{phase} ')
    name = NAMES.get(phase, '?')

    # Token stats + truncation check
    stats = ''
    warn = ''
    sf = d / 'processing_stats.json'
    if sf.exists():
        try:
            s = json.loads(sf.read_text(encoding='utf-8'))
            summ = s.get('summary', {})
            tok = summ.get('total_tokens', 0)
            cost = summ.get('total_cost_usd', 0)
            if tok: stats = f'  [{tok:,} tok'
            if cost: stats += f', \${cost:.2f}'
            if tok: stats += ']'
            # Truncation detection
            for k, v in s.items():
                if k == 'summary' or not isinstance(v, dict): continue
                out_tok = v.get('output_tokens', 0)
                max_tok = v.get('max_tokens', 0)
                if max_tok and out_tok >= max_tok - 100 and out_tok > 10000:
                    warn = f'  !! TRUNCATION faze {k} ({out_tok}/{max_tok})'
                    truncated.append(f'{d.name} faze {k}')
        except: pass

    print(f'[{icon}] {d.name:55s} Faze {phase:2d} ({name:12s}){stats}{warn}')
    counts[phase] = counts.get(phase, 0) + 1
    total += 1

print(f'\n--- Celkem: {total} clanku ---')
for p in sorted(counts):
    if counts[p] > 0:
        label = NAMES.get(p, 'Zadna faze' if p == -1 else '?')
        print(f'  Faze {p:2d} ({label}): {counts[p]}')
if truncated:
    print(f'\n!! TRUNCATION WARNINGS ({len(truncated)}):')
    for t in truncated: print(f'  - {t}')
"
```

Pokud uzivatel zadal argument, predej ho jako `$ARGUMENTS`. Zobraz vysledek jako tabulku.
Pokud jsou truncation warnings, upozorni uzivatele a navrhni `--from-phase` reprocessing.
