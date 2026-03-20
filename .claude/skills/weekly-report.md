---
name: weekly-report
description: "Týdenní přehled zpracovaných článků, nákladů a statistik NG-ROBOT. Použij když uživatel říká 'týdenní report', 'weekly report', 'co se udělalo za týden', 'přehled za týden', 'souhrn práce', nebo chce vidět aktivitu za časové období. NEPOUŽÍVEJ pro status jednoho článku (použij article-status) nebo pro tokeny bez časového rozsahu (použij token-stats)."
argument-hint: "[YYYY-MM-DD | days:N]"
effort: medium
---

# Weekly Report — týdenní přehled NG-ROBOT

Generuje strukturovaný přehled aktivity za poslední týden (nebo zadané období).

## Co report obsahuje

### 1. Zpracované články
- Projít `processed/` — složky s datem v názvu (`YYYY-MM-DD_*`)
- Filtrovat podle data (posledních 7 dní, nebo uživatelem zadané období)
- Pro každý článek: název, rubrika, fáze (dokončen/rozpracován), zdroj (RSS/inbox)

### 2. Tokenová spotřeba a náklady
- Přečíst `token_usage.json` v každé složce článku
- Sečíst input/output tokeny per model (Haiku/Sonnet/Opus)
- Spočítat cenu podle aktuálních sazeb:
  - Haiku 4.5: $0.80/$4.00 per 1M tokens (input/output)
  - Sonnet 4.6: $3.00/$15.00 per 1M tokens
  - Opus 4.6: $15.00/$75.00 per 1M tokens

### 3. CMS Aqua publikace
- Přečíst `.cms_published.json` — filtrovat za období
- Počet publikovaných vs zpracovaných

### 4. Chyby a problémy
- Hledat `.processing_state.json` se statusem `error` nebo `stuck`
- Články bez `9_final.md` (nedokončené)

## Výstupní formát

```markdown
# 📊 Týdenní report NG-ROBOT (DD.MM. – DD.MM.YYYY)

## Články
| # | Datum | Článek | Rubrika | Status | CMS |
|---|-------|--------|---------|--------|-----|
| 1 | 10.3. | Název článku | Příroda | ✅ Hotovo | ✅ |
| 2 | 11.3. | Jiný článek | Věda | ⚠️ Fáze 5 | ❌ |

**Celkem:** X dokončených, Y rozpracovaných

## Náklady
| Model | Input tokens | Output tokens | Cena |
|-------|-------------|---------------|------|
| Haiku | ... | ... | $X.XX |
| Sonnet | ... | ... | $X.XX |
| Opus | ... | ... | $X.XX |
| **Celkem** | | | **$X.XX** |

## CMS Aqua
Publikováno: X / Y zpracovaných

## Problémy
- [pokud jsou]
```

## Postup generování

1. Zjistit časový rozsah (default: posledních 7 dní)
2. Projít `processed/` — glob `YYYY-MM-DD_*` složky
3. Pro každou složku v rozsahu:
   - Přečíst `metadata.json` (rubrika, název)
   - Zkontrolovat existenci `9_final.md`
   - Přečíst `token_usage.json` (tokeny)
4. Přečíst `.cms_published.json` — filtrovat za období
5. Přečíst `.processing_state.json` — najít chyby
6. Sestavit a vypsat report
