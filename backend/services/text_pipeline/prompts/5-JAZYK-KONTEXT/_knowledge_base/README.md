# KVP - Kontextuální verifikace překladu

**Verze:** 1.0  
**Účel:** Kontrola překladových a kontextuálních chyb, které unikají standardním kontrolám

---

## 🎯 O PROJEKTU

Tento projekt zachycuje chyby v překladech, které jsou:
- ✅ Gramaticky správné
- ✅ Stylisticky neutrální  
- ✅ Fakticky neověřitelné
- ❌ Ale **sémanticky chybné** nebo **kontextuálně nevhodné**

**Typický příklad:** „starověký člověk" pro fosilie staré 773 000 let (správně: pravěký)

---

## 📁 OBSAH BALÍČKU

| Soubor | Popis |
|--------|-------|
| `MASTER_INSTRUCTIONS.md` | Hlavní instrukce a workflow projektu (12 kategorií kontrol) |
| `TRANSLATION_TRAPS.md` | Databáze false friends a problematických párů EN-CS |
| `TEMPORAL_TERMINOLOGY.md` | Terminologie epoch a historických období |
| `IDIOMS_DATABASE.md` | Databáze idiomů a jejich českých ekvivalentů |
| `COLLOCATIONS_GUIDE.md` | Průvodce českými kolokacemi |
| `TERMINOLOGY_ACCESSIBILITY.md` | **NOVÉ:** Srozumitelnost odborné terminologie pro laiky |
| `ANGLICISMS_AND_CALQUES.md` | **NOVÉ:** Anglicismy a syntaktické kalky |
| `TRANSLITERATION_RULES.md` | **NOVÉ:** Pravidla transliterace pro URL (ě→e, NE i!) |
| `EXAMPLES.md` | Příklady nálezů a oprav z praxe |

---

## 🚀 RYCHLÝ START

### 1. Vytvoř nový Claude projekt
- Název: `KVP - Kontextuální verifikace překladu`
- Nahraj všechny soubory z tohoto balíčku

### 2. Nastav instrukce projektu
Zkopíruj obsah `MASTER_INSTRUCTIONS.md` do instrukcí projektu.

### 3. Spusť kontrolu
```
Proveď kontextuální verifikaci následujícího překladu podle KVP workflow:

[VLOŽIT TEXT]
```

---

## 📋 KATEGORIE KONTROL (12)

1. **Translation Traps** - False friends (ancient ≠ starověký)
2. **Temporální kontext** - Epochy a období (pravěk vs. starověk)
3. **Idiomy** - Ustálená spojení (tip of the iceberg)
4. **Kolokace** - Slovní spojení (make a decision → přijmout rozhodnutí)
5. **Registr** - Stylistická konzistence
6. **Kulturní reference** - Srozumitelnost pro CZ čtenáře
7. **Logická konzistence** - Vnitřní logika textu
8. **Srozumitelnost terminologie** - Odborné termíny pro laiky (graciálnost → jemnost)
9. **Anglicismy** - Zbytečné anglicismy (implementovat → zavést)
10. **Syntaktické kalky** - Anglické konstrukce (pasivum, nominalizace)
11. **Transliterace** - URL a identifikátory (ě→e, NE i!)
12. **Vědecká komunikace** - Srozumitelnost pro laiky

---

## 🔴 PRIORITA NÁLEZŮ

| Úroveň | Kritérium | Akce |
|--------|-----------|------|
| 🔴 KRITICKÁ | Mění význam / fakticky nepravdivé | MUSÍ být opraveno |
| 🟡 DŮLEŽITÁ | Zní nepřirozeně / může zmást | Doporučeno opravit |
| 🟢 DROBNÁ | Existuje lepší alternativa | Zvážit |

---

## 📊 FORMÁT VÝSTUPU

```markdown
# KVP REPORT

## NÁLEZY

### 🔴 KRITICKÉ
| # | Typ | Původní | Problém | Oprava |
|---|-----|---------|---------|--------|
| 1 | Translation trap | starověký člověk | 773 000 let = pravěk | pravěký člověk |

### 🟡 DŮLEŽITÉ
...

### 🟢 DROBNÉ
...

## VERDIKT
[ ] ✅ SCHVÁLENO
[ ] ⚠️ PODMÍNĚNĚ SCHVÁLENO
[ ] ❌ VRÁCENO
```

---

## 🔗 INTEGRACE S DALŠÍMI PROJEKTY

KVP je navržen jako **poslední kontrolní fáze** po:
1. Gramatické kontrole
2. Stylistické kontrole
3. Faktické kontrole
4. Bio-terminologické kontrole (BioLib)

---

## 📝 ROZŠIŘOVÁNÍ DATABÁZÍ

Databáze jsou navrženy k průběžnému rozšiřování:
- Při nalezení nového false friend → přidej do `TRANSLATION_TRAPS.md`
- Při nalezení nového idiomu → přidej do `IDIOMS_DATABASE.md`
- Při zajímavém nálezu → přidej do `EXAMPLES.md`

---

## ⚠️ OMEZENÍ

- KVP **nenahrazuje** gramatickou a stylistickou kontrolu
- KVP **nekontroluje** faktickou správnost tvrzení
- KVP **nevyhledává** chybějící informace

---

**Verze:** 1.0  
**Vytvořeno:** 08.01.2026  
**Autor:** Claude
