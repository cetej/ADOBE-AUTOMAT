---
name: reprocess
description: Prepracovani clanku od konkretni faze v NG-ROBOT pipeline. Pouzij kdyz uzivatel chce "prepracovat", "reprocess", "spustit znovu od faze", "opravit clanek od faze 5", nebo "from-phase". Vyzaduje cislo faze (0-9) a slug clanku. Pred spustenim VZDY zepta na potvrzeni.
argument-hint: "<phase-number> <article-slug>"
tags: [articles, processing, reprocess]
---

Prepracuj clanek od zadane faze. Parsuj argument `$ARGUMENTS`:
- Prvni cislo = cislo faze (0-9)
- Zbytek = slug nebo cast nazvu slozky v `processed/`

## Postup

1. Najdi slozku v `processed/` ktera odpovida zadanemu slugu:
```bash
ls -d "C:/Users/stock/Documents/000_NGM/NG-ROBOT/processed/"*SLUG* 2>/dev/null
```

2. Pokud existuje vice shod, zobraz je a zeptej se uzivatele.

3. Pokud je presne jedna shoda, zobraz prikaz a ZEPTEJ SE na potvrzeni:
```
Spustim: python ngrobot.py --from-phase N "processed/FOLDER"
Pokracovat? (ano/ne)
```

4. Po potvrzeni spust:
```bash
cd "C:/Users/stock/Documents/000_NGM/NG-ROBOT" && python ngrobot.py --from-phase N "processed/FOLDER"
```

## Pravidla
- BEZ potvrzeni uzivatele NIKDY nespoustej processing
- Pokud chybi argument, zeptej se: "Zadej cislo faze a cast nazvu clanku, napr.: /reprocess 5 coral-reef"
- Faze 0-9 jsou validni, cokoliv jineho odmitni
