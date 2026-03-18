# Implementation Plan — Watch News Action Items

**Created**: 2026-03-18
**Source**: /watch full scan action items + watch list
**Status**: DRAFT — awaiting approval

---

## Overview

Zbývající akce vyplývající z /watch scanu, které nebyly součástí orchestrační infrastruktury.

Dvě kategorie:
- **Projektové závislosti** — Python, PyTorch, timm, diffusers upgrade
- **Orchestrační automatizace** — skutečná konfigurace hooků, plugin research
- **Research** — nové papers a techniky relevantní pro Pyramid Flow

---

## 1. Upgrade závislostí (CRITICAL)

### 1a. Python 3.8.10 → 3.10+

**Proč**: Python 3.8 je EOL (říjen 2024). Diffusers 0.37+, novější PyTorch, i timm 1.x vyžadují 3.10+. Bez tohoto je celý dependency stack zamrzlý.

**Co udělat**:
1. Aktualizovat setup instrukce v CLAUDE.md: `python==3.8.10` → `python==3.10.14`
2. Prohledat kód na Python 3.8-specifické patterny (walrus operator je OK od 3.8, ale zkontrolovat `match/case` absence atd.)
3. Zkontrolovat `spacy==3.7.5` kompatibilitu s Python 3.10
4. Aktualizovat README / setup instrukce pokud existují

**Effort**: small (samotný kód pravděpodobně funguje, je to hlavně konfigurace)

### 1b. PyTorch 2.1.2 → 2.5.x (konzervativní)

**Proč**: 8 major verzí pozadu. Nové verze mají FlashAttention-2 built-in, lepší compile(), SDPA improvements.

**Co udělat**:
1. Spustit `/dependency-audit torch` pro identifikaci breaking changes
2. Zkontrolovat `torch.compile()` kompatibilitu s naším DiT modelem
3. Aktualizovat `requirements.txt`: `torch==2.5.1`, `torchvision==0.20.1`
4. Ověřit `accelerate` kompatibilitu (pravděpodobně potřeba bump na 0.34+)
5. Hledat deprecated API: `torch.cuda.amp` → `torch.amp`, atd.

**Proč ne 2.10?**: Příliš velký skok. 2.5.x je stabilní a přináší hlavní výhody bez rizika.

**Effort**: medium (nutná analýza breaking changes v DiT a VAE kódu)

### 1c. timm 0.6.12 → 0.9.x (konzervativní)

**Proč**: Masivní verze gap. Ale 1.0.x je breaking — jiné API pro vytváření modelů.

**Co udělat**:
1. Spustit `/dependency-audit timm`
2. Grepit kód na `timm.create_model`, `timm.models` — zjistit co přesně používáme
3. Zjistit minimální verzi timm potřebnou pro naše use-cases
4. Pokud používáme jen LPIPS/perceptual features → možná stačí 0.9.x bez breaking changes

**Effort**: medium (závisí na rozsahu použití timm v kódu)

### 1d. diffusers >=0.30.1 → >=0.35.0

**Proč**: Modular Diffusers, lepší scheduler API, bugfixy. Nepůjdeme na 0.37 hned (vyžaduje Python 3.10, ale hlavně velké API changes).

**Co udělat**:
1. Spustit `/dependency-audit diffusers`
2. Zkontrolovat `scheduling_flow_matching.py` — dědí z diffusers base classes?
3. Zkontrolovat `export_to_video` API changes
4. Aktualizovat `requirements.txt`

**Effort**: small-medium

### 1e. transformers 4.39.3 → 4.44.x

**Co udělat**:
1. Zkontrolovat `modeling_text_encoder.py` — používá SD3 text encoder z transformers
2. Ověřit zpětnou kompatibilitu T5/CLIP encoder API
3. Aktualizovat `requirements.txt`

**Effort**: small

### Pořadí upgradů (dependency chain):

```
Fáze 1: Python 3.8 → 3.10        (odblokuje vše ostatní)
Fáze 2: torch 2.1 → 2.5           (+ torchvision, accelerate)
         ↕ paralelně
         transformers 4.39 → 4.44
Fáze 3: diffusers 0.30 → 0.35     (závisí na torch + transformers)
         ↕ paralelně
         timm 0.6 → 0.9
Fáze 4: numpy, spacy, opencv      (minor bumps for compatibility)
```

---

## 2. Konfigurace hooků

### 2a. TaskCompleted hook

**Co**: Skutečně nakonfigurovat hook v settings.json (ne jen doporučení v CLAUDE.md).

**Akce**:
```json
// .claude/settings.local.json
{
  "hooks": {
    "TaskCompleted": [{
      "type": "command",
      "command": "echo '📋 Task done. Consider: /scribe complete, /checkpoint save'"
    }]
  }
}
```

**Pozn.**: Potřeba ověřit, zda `TaskCompleted` event existuje v aktuální verzi Claude Code. /watch to reportoval, ale nebylo ověřeno hands-on.

### 2b. SessionStart hook pro checkpoint

**Co**: Automaticky zobrazit checkpoint při startu session.

**Akce**:
```json
{
  "hooks": {
    "SessionStart": [{
      "type": "command",
      "command": "if [ -f .claude/memory/checkpoint.md ]; then echo '⚡ Checkpoint found:'; head -10 .claude/memory/checkpoint.md; fi"
    }]
  }
}
```

**Effort**: small (obojí)

---

## 3. Plugin System Research

### 3a. Prozkoumat Claude Code Plugin format

**Co**: Zjistit, zda naše orchestrační skilly (.claude/skills/) lze zabalit jako distribuovatelný plugin.

**Akce**:
1. WebSearch: `"claude code" plugin format packaging 2026`
2. WebFetch dokumentace pluginového systému
3. Sepsat findings do `.claude/memory/plugin-research.md`
4. Rozhodnout: stojí za to? Nebo je `.claude/skills/` v repo dostatečné?

**Effort**: small (jen research)

---

## 4. Research — nové techniky pro Pyramid Flow

### 4a. Self-Flow paper analýza

**Co**: Přečíst a zhodnotit Self-Supervised Flow Matching paper — je Dual-Timestep Scheduling aplikovatelný na Pyramid Flow?

**Akce**:
1. WebFetch arxiv paper
2. Porovnat s naším `scheduling_flow_matching.py`
3. Sepsat findings — jestli je technika adaptovatelná a co by to vyžadovalo

### 4b. Transition Matching Distillation analýza

**Co**: Zhodnotit TMD pro zrychlení inference Pyramid Flow (méně kroků → rychlejší generování).

**Akce**:
1. WebFetch paper
2. Porovnat s naším Euler discrete schedulerem
3. Odhadnout effort pro implementaci

### 4c. Modular Diffusers kompatibilita

**Co**: Zjistit, zda Pyramid Flow pipeline může benefitovat z Modular Diffusers architektury.

**Akce**:
1. WebFetch HuggingFace blog post
2. Porovnat s `pyramid_dit_for_video_gen_pipeline.py` architekturou
3. Rozhodnout: migrace na modular diffusers vs. zachování vlastní pipeline

**Effort**: medium celkem (3 research tasky, každý ~15-20k tokenů)

---

## Navrhované pořadí

```
Fáze 1 — Rychlé akce (small effort):
  2a. TaskCompleted hook konfigurace
  2b. SessionStart hook konfigurace
  3a. Plugin System research

Fáze 2 — Dependency upgrades (medium-high effort):
  1a. Python 3.10 upgrade
  1b. PyTorch 2.5 upgrade
  1e. transformers upgrade
  1d. diffusers upgrade
  1c. timm upgrade

Fáze 3 — Research (medium effort, nezávislé):
  4a. Self-Flow paper  ← paralelně
  4b. TMD paper         ← paralelně
  4c. Modular Diffusers ← paralelně
```

**Estimated complexity**: standard tier pro Fázi 1+2, light pro Fázi 3 (research only)

---

## Open Questions

1. **Testování upgradů**: Projekt nemá testy. Jak ověříme, že upgrady nic nerozbily? → Spustit inference pipeline na jednom promptu a porovnat výstup?
2. **Python 3.10 vs 3.12**: Konzervativně 3.10 (minimální viable), nebo rovnou 3.12? → Doporučuji 3.10 (nejmenší riziko, odblokuje vše)
3. **PyTorch 2.5 vs 2.10**: Konzervativně 2.5 (stable), nebo agresivně 2.10? → 2.5 jako první krok
4. **Pořadí research vs upgrades**: Dělat research paralelně s upgrady, nebo nejdřív upgrady? → Upgrady mají vyšší prioritu, research může paralelně
