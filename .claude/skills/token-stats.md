---
name: token-stats
description: Tokenova spotreba a odhad nakladu za zpracovane clanky v NG-ROBOT. Pouzij kdyz uzivatel rika "kolik to stalo", "naklady", "tokeny", "cost", "spotreba", "kolik stoji clanek", "cena zpracovani". Zobrazi per-model a per-clanek breakdown s cenami v USD.
argument-hint: "[article-slug]"
effort: low
tags: [analytics, tokens, cost]
---

Zobraz tokenovou statistiku. Spust tento Python skript v Bash:

```bash
cd "C:/Users/stock/Documents/000_NGM/NG-ROBOT" && python -c "
import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
from collections import defaultdict

arg = '$ARGUMENTS'.strip()
processed = Path('processed')
if not processed.exists():
    print('Slozka processed/ neexistuje'); sys.exit(1)

# Ceny per 1M tokenu (input/output)
PRICES = {
    'claude-opus-4-6': (15.0, 75.0),
    'claude-sonnet-4-6': (3.0, 15.0),
    'claude-haiku-4-5-20251001': (0.80, 4.0),
}

model_totals = defaultdict(lambda: {'input': 0, 'output': 0, 'cost': 0.0, 'calls': 0})
article_totals = []

for d in sorted(processed.iterdir(), reverse=True):
    if not d.is_dir() or d.name.startswith('.'): continue
    if arg and arg not in d.name: continue

    sf = d / 'processing_stats.json'
    if not sf.exists(): continue

    try:
        s = json.loads(sf.read_text(encoding='utf-8'))
    except: continue

    art_input = art_output = 0
    art_cost = 0.0
    art_phases = 0

    for k, v in s.items():
        if k == 'summary' or not isinstance(v, dict): continue
        model = v.get('model', 'unknown')
        inp = v.get('input_tokens', 0)
        out = v.get('output_tokens', 0)

        # Odhad ceny
        price_in, price_out = PRICES.get(model, (3.0, 15.0))
        cost = (inp * price_in + out * price_out) / 1_000_000

        model_totals[model]['input'] += inp
        model_totals[model]['output'] += out
        model_totals[model]['cost'] += cost
        model_totals[model]['calls'] += 1

        art_input += inp
        art_output += out
        art_cost += cost
        art_phases += 1

    if art_phases > 0:
        elapsed = s.get('summary', {}).get('total_elapsed_seconds', 0)
        article_totals.append((d.name, art_input, art_output, art_cost, art_phases, elapsed))

# Per-article detail (pokud filtrujeme nebo mene nez 20)
if arg or len(article_totals) <= 20:
    print('=== CLANKY ===')
    for name, inp, out, cost, phases, elapsed in article_totals:
        time_str = f'{elapsed/60:.0f}min' if elapsed else '?'
        print(f'{name:55s} {inp+out:>10,} tok  \${cost:>6.2f}  {phases} fazi  {time_str}')
    print()

# Souhrn per model
print('=== MODELY ===')
total_cost = 0
for model, data in sorted(model_totals.items()):
    total = data['input'] + data['output']
    print(f'{model:40s} {total:>12,} tok  (in:{data[\"input\"]:,} out:{data[\"output\"]:,})  \${data[\"cost\"]:>8.2f}  {data[\"calls\"]} volani')
    total_cost += data['cost']

print(f'\n=== CELKEM ===')
total_tok = sum(d['input']+d['output'] for d in model_totals.values())
total_calls = sum(d['calls'] for d in model_totals.values())
print(f'Tokeny: {total_tok:,}  |  Naklady: \${total_cost:.2f}  |  Volani: {total_calls}  |  Clanku: {len(article_totals)}')
if article_totals:
    avg = total_cost / len(article_totals)
    print(f'Prumer na clanek: \${avg:.2f}')
"
```

Zobraz vysledek. Pokud uzivatel zadal slug, filtruj. Jinak zobraz souhrn.
