# 📋 Kompletní Workflow - Stylistický Editor Překládaných Článků v2.2

## 🎯 Účel projektu

Systematická identifikace a oprava stylistických nedostatků v článcích přeložených z angličtiny do češtiny pro National Geographic CZ.

---

## 📦 Struktura souborů projektu

```
Stylisticky-Editor-v2.2/
│
├── 🔴 POVINNÉ (pro fungování)
│   ├── CUSTOM_INSTRUCTIONS_v2_2.txt    ← Hlavní instrukce pro Claude
│   └── InteractiveStyleEditor_v2_WORKING_TEMPLATE.jsx  ← Funkční šablona
│
├── 🟡 DOKUMENTACE
│   ├── DOKUMENTACE.md                  ← Kompletní příručka
│   ├── QUICK_START_v2_1.md            ← Rychlý průvodce
│   ├── PRIKLAD_POUZITI.md             ← Praktické scénáře
│   ├── TAHAK.md                       ← Rychlá reference
│   └── FILES_OVERVIEW.txt             ← Přehled souborů
│
├── 🟢 TROUBLESHOOTING
│   └── TROUBLESHOOTING_BILA_PLOCHA.md ← Řešení problémů
│
└── 🔵 ŠABLONY (reference)
    ├── InteractiveStyleEditor.jsx      ← Původní verze
    ├── InteractiveStyleEditor_v2.jsx   ← Verze 2 (pozor: dynamické třídy)
    └── InteractivniStylistickaKontrola.jsx ← Tutanchamon template
```

---

## 🔄 KOMPLETNÍ WORKFLOW

### FÁZE 1: Příprava prostředí

```
┌─────────────────────────────────────────────────────────────┐
│  1. NASTAVENÍ CLAUDE PROJECTS                               │
│                                                             │
│  ○ Vytvoř nový projekt v Claude.ai                         │
│  ○ Zkopíruj CUSTOM_INSTRUCTIONS_v2_2.txt do instrukcí      │
│  ○ Nahraj dokumentaci do Knowledge Base                     │
│                                                             │
│  Čas: 5 minut                                               │
└─────────────────────────────────────────────────────────────┘
```

### FÁZE 2: Vstup článku

```
┌─────────────────────────────────────────────────────────────┐
│  2. ZADÁNÍ ČLÁNKU KE KONTROLE                               │
│                                                             │
│  Příkaz:                                                    │
│  "Zkontroluj stylistiku tohoto článku:                     │
│   [vložit text článku]"                                     │
│                                                             │
│  Volitelné parametry:                                       │
│  • Typ textu (blog/technický/PR)                           │
│  • Cílová skupina                                           │
│  • Úroveň kontroly (konzervativní/standardní/agresivní)    │
└─────────────────────────────────────────────────────────────┘
```

### FÁZE 3: Analýza (Claude)

```
┌─────────────────────────────────────────────────────────────┐
│  3. AUTOMATICKÁ ANALÝZA                                     │
│                                                             │
│  Claude provede:                                            │
│                                                             │
│  ① Identifikace problémů                                   │
│     • Anglicismy                    🔴 vysoká priorita     │
│     • Slovosled                     🟡 vysoká priorita     │
│     • Trpný rod                     🟠 střední priorita    │
│     • Složitá souvětí               🔵 střední priorita    │
│     • Idiomy                        🟣 nízká priorita      │
│                                                             │
│  ② Prioritizace podle závažnosti                           │
│                                                             │
│  ③ Generování variant oprav (2-3 pro každý problém)       │
│                                                             │
│  ④ Příprava vzdělávacích vysvětlení                       │
└─────────────────────────────────────────────────────────────┘
```

### FÁZE 4: Výstupy (2 artefakty)

```
┌─────────────────────────────────────────────────────────────┐
│  4A. INTERAKTIVNÍ EDITOR (.jsx)                             │
│                                                             │
│  React komponenta obsahující:                               │
│  • Header se statistikami                                   │
│  • Seznam všech problémů s barevným kódováním              │
│  • Varianty řešení (radio buttons)                         │
│  • Pole pro vlastní variantu                                │
│  • Vysvětlení každého problému                             │
│  • Souhrn změn + tlačítko pro kopírování                   │
│                                                             │
│  Pro: Detailní interaktivní práci                          │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  4B. OPTIMÁLNÍ SEZNAM ÚPRAV (.md)                           │
│                                                             │
│  Markdown dokument obsahující:                              │
│  • Přehled statistik                                        │
│  • Číslovaný seznam všech oprav                            │
│  • Původní text → Doporučená oprava                        │
│  • Zdůvodnění každého výběru                               │
│  • Shrnutí přínosů                                          │
│                                                             │
│  Pro: Rychlou aplikaci změn bez interakce                  │
└─────────────────────────────────────────────────────────────┘
```

### FÁZE 5: Rozhodnutí uživatele

```
┌─────────────────────────────────────────────────────────────┐
│  5. VÝBĚR PRACOVNÍHO POSTUPU                                │
│                                                             │
│  MOŽNOST A: Použít interaktivní editor                     │
│  ├─ Projít každý problém                                    │
│  ├─ Vybrat preferovanou variantu                           │
│  ├─ Případně napsat vlastní                                 │
│  └─ Zkopírovat seznam změn                                  │
│                                                             │
│  MOŽNOST B: Použít optimální seznam                        │
│  ├─ Přečíst doporučení                                      │
│  ├─ Případně upravit některé položky                       │
│  └─ Potvrdit aplikaci změn                                  │
│                                                             │
│  MOŽNOST C: Kombinace                                       │
│  ├─ Začít s optimálním seznamem                            │
│  └─ Doladit v interaktivním editoru                        │
└─────────────────────────────────────────────────────────────┘
```

### FÁZE 6: Aplikace změn

```
┌─────────────────────────────────────────────────────────────┐
│  6. VYTVOŘENÍ OPRAVENÉ VERZE                                │
│                                                             │
│  Příkaz:                                                    │
│  "Vytvoř opravenou verzi článku s těmito změnami:          │
│   [vložit seznam změn]"                                     │
│                                                             │
│  Claude vytvoří:                                            │
│  • Nový artifact (.md nebo .html)                          │
│  • Kompletní opravený článek                                │
│  • Zachované formátování                                    │
│  • Připraveno ke zkopírování/exportu                       │
└─────────────────────────────────────────────────────────────┘
```

### FÁZE 7: Finalizace

```
┌─────────────────────────────────────────────────────────────┐
│  7. EXPORT A POUŽITÍ                                        │
│                                                             │
│  • Zkopírovat opravený text do CMS                         │
│  • Stáhnout jako soubor                                     │
│  • Případná další iterace (doplňující kontrola)            │
│                                                             │
│  Kontrolní checklist:                                       │
│  □ Všechny vysoké priority vyřešeny                        │
│  □ Faktický obsah zachován                                  │
│  □ Text působí přirozeně česky                             │
│  □ Formátování je v pořádku                                │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Vizuální diagram workflow

```
                    ┌──────────────┐
                    │   ČLÁNEK     │
                    │  (vstup)     │
                    └──────┬───────┘
                           │
                           ▼
              ┌────────────────────────┐
              │    ANALÝZA CLAUDE      │
              │  • Identifikace        │
              │  • Prioritizace        │
              │  • Varianty            │
              └───────────┬────────────┘
                          │
            ┌─────────────┴─────────────┐
            │                           │
            ▼                           ▼
   ┌─────────────────┐       ┌─────────────────┐
   │  INTERAKTIVNÍ   │       │   OPTIMÁLNÍ     │
   │    EDITOR       │       │    SEZNAM       │
   │    (.jsx)       │       │    (.md)        │
   └────────┬────────┘       └────────┬────────┘
            │                         │
            └──────────┬──────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │   ROZHODNUTÍ    │
              │   UŽIVATELE     │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │    OPRAVENÁ     │
              │     VERZE       │
              │   (výstup)      │
              └─────────────────┘
```

---

## 🎨 Typy problémů a priority

| Emoji | Typ | Priorita | Příklad |
|-------|-----|----------|---------|
| 🔴 | Anglicismus | VYSOKÁ | realizovat → uskutečnit |
| 🟡 | Slovosled | VYSOKÁ | Je to důležité → Je důležité |
| 🟠 | Trpný rod | STŘEDNÍ | Bylo zjištěno → Zjistili jsme |
| 🔵 | Složité souvětí | STŘEDNÍ | Rozdělení na kratší věty |
| 🟣 | Idiom | NÍZKÁ | na konci dne → nakonec |

---

## ⚡ Rychlé příkazy

| Příkaz | Účel |
|--------|------|
| `Zkontroluj stylistiku článku:` | Standardní kontrola |
| `Zkontroluj konzervativně:` | Minimální změny |
| `Zkontroluj agresivně:` | Maximální přirozenost |
| `Zkontroluj pouze anglicismy:` | Specifický typ |
| `Udělej jen seznam doporučených oprav:` | Pouze markdown seznam |
| `Vytvoř opravenou verzi s těmito změnami:` | Finální verze |

---

## ⚠️ Kritické body

### Uvozovky v datech (prevence bílé plochy)
```javascript
// ❌ ŠPATNĚ
orig: "text s „citací""

// ✅ SPRÁVNĚ  
orig: 'text s „citací"'
```

### Tailwind CSS třídy
```javascript
// ❌ ŠPATNĚ - dynamické
className={`bg-${color}-500`}

// ✅ SPRÁVNĚ - statické
let bgClass = 'bg-red-500';
if (color === 'orange') bgClass = 'bg-orange-500';
```

---

## 📁 Doporučené pořadí čtení dokumentace

1. **QUICK_START_v2_1.md** - Rychlý start (10 min)
2. **TAHAK.md** - Reference příkazů
3. **PRIKLAD_POUZITI.md** - Praktické scénáře
4. **DOKUMENTACE.md** - Kompletní příručka
5. **TROUBLESHOOTING_BILA_PLOCHA.md** - Řešení problémů

---

## 🔧 Řešení běžných problémů

| Problém | Řešení |
|---------|--------|
| Bílá plocha v editoru | Zkontroluj uvozovky + dynamické třídy |
| Příliš mnoho změn | `Ukaž jen vysokou prioritu` |
| Mění odborné termíny | `Zachovej terminologii [oblast]` |
| Chci víc variant | `U problému X dej víc možností` |

---

## 📈 Verze

| Verze | Datum | Hlavní změny |
|-------|-------|--------------|
| 1.0 | 10/2025 | Základní editor |
| 2.0 | 10/2025 | Moderní UI, gradienty, statistiky |
| 2.1 | 24.10.2025 | Bezpečnostní pravidla pro uvozovky |
| **2.2** | **30.10.2025** | **Automatický optimální seznam úprav** |

---

**Autor:** Claude AI + webeditor  
**Poslední aktualizace:** 30. 10. 2025  
**Verze dokumentu:** 2.2
