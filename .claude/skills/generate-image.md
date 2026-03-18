---
name: generate-image
description: Generovani obrazku pro ZPRACOVANY clanek v NG-ROBOT pipeline (processed/ slozka). Cte visual_brief z 0_analysis.json a VISUAL_REFERENCE.md, navrhnne 3 koncepty a generuje pres ImageGenerator (Nano Banana Pro). Pouzij POUZE kdyz uzivatel chce obrazek ke KONKRETNIMU clanku v processed/ — napr. "/generate-image coral-reef hero", "udelej hero k clanku o...", "ilustrace pro clanek...". NEPOUZIVEJ pro obecne prompty bez clanku (pouzij image-prompt-generator) nebo pro infografiky s pozicovanim prvku (pouzij visual-data-architect).
argument-hint: "<article-slug> [hero|illustration|infographic]"
tags: [images, generation, visual]
---

# Generate Image for Article

Generuje obrazek pro clanek pres ImageGenerator (Nano Banana Pro / Gemini).

## Parsovani argumentu

Z `$ARGUMENTS` extrahuj:
- **slug** — cast nazvu slozky v `processed/`
- **typ** — `hero`, `illustration`, `infographic` (vychozi: `illustration`)

## Postup

### 1. Najdi clanek

```bash
ls -d "C:/Users/stock/Documents/000_NGM/NG-ROBOT/processed/"*SLUG* 2>/dev/null
```

Pokud vice shod, zobraz a zeptej se. Pokud zadna, hledej v `articles/`.

### 2. Nacti vizualni brief z faze 0

Precti `0_analysis.json` ve slozce clanku. Extrahuj sekci `visual_brief`:
- `dominant_tone` — urcuje paletu a osvetleni
- `color_direction` — slovni popis barevneho smeru
- `visual_subjects` — konkretni fotografovatelne objekty
- `key_visual_moment` — "punctuation point" pro hero
- `setting` — prostredi
- `human_element` — lidsky rozmer
- `recommended_style` — doporuceny vizualni styl
- `hero_concept` — navrh hero image z analyzy
- `infographic_potential` — vhodnost pro infografiku

Pokud `0_analysis.json` neexistuje nebo nema `visual_brief`, precti finalní clanek (9_final.md nebo 6_stylized.md) a analyzuj manualne.

### 3. Precti vizualni referenci

Precti `C:/Users/stock/Documents/000_NGM/NG-ROBOT/projects/VISUAL_REFERENCE.md`:
- Najdi radek pro `dominant_tone` v tabulce "Mapovani tonu → vizualni jazyk"
- Najdi barevnou paletu pro tema clanku v "Barevne palety dle tematu"
- Pouzij prompt fragment pro dany ton

### 4. Navrhni 3 koncepty (A/B/C)

Navrhni 3 odlisne vizualni koncepty. Zadne sablony — kazdy koncept by mel vychazet z obsahu clanku, vizualniho briefu a toho, co bude nejsilnejsi jako obrazek. Muze to byt cokoliv: detail, krajina, portret, abstrakce, kolaz, letecky pohled, podvodni scena, split-view...

Dulezite je, aby se koncepty vzajemne lisily (jiny uhel pohledu, jina nalada, jiny subjekt) a daly uzivateli skutecny vyber.

Pro kazdou variantu zobraz:
1. Kratky nazev (3-5 slov) + popis kompozice (1-2 vety)
2. **Nano Banana Pro JSON** — detailni strukturovany prompt (vycerpi vizualni brief)
3. **Midjourney fallback** — 30-50 slov, `--ar ASPECT`

**Dva formaty promptu (vzdy oba):**

**A) Nano Banana Pro (primarni)** — strukturovany JSON prompt, az 15 000 znaku:
- Detailni popis sceny, materialu, osvetleni, textury, atmosfery
- Konkretni barevne kody z palety (hex)
- Kompozicni instrukce (popredi/stredy/pozadi, pomery ploch)
- Technicke parametry (rozliseni, aspect ratio, styl renderovani)
- Negativni prompt (co nechceme)
- Format: JSON objekt s klici `prompt`, `negative_prompt`, `aspect_ratio`, `style`

**B) Midjourney fallback** — cisty textovy prompt, 30-50 slov anglicky:
- Kondenzovana verze pro pripad, ze Nano Banana neni dostupny
- Zakonci `--ar ASPECT`

**Spolecna pravidla pro oba formaty:**
- VZDY anglicky (Gemini generuje lepe z EN promptu)
- Zadny text, loga, vodoznaky v obrazku
- Konkretni objekty — zadne abstrakce, grafy, diagramy
- Editorial kvalita: dramaticke svetlo, textury, vysoka definice
- KAZDE slovo musi nest informaci — zadne "beautiful", "amazing", "stunning"

**Aspect ratio:**
- Vychozi: hero 3:2, ilustrace 16:9, infografika 4:3
- Uzivatel muze zadat libovolny pomer (napr. 1:1, 9:16, 21:9) — pouzij ho
- Pokud nezada, navrhni vhodny pomer na zaklade kompozice a zeptej se

### 5. Zeptej se uzivatele

Zobraz koncepty v tomto formatu:
- Kratky nazev (3-5 slov) + popis kompozice (1-2 vety)
- Nano Banana Pro JSON prompt (plny, strukturovany)
- Midjourney fallback (30-50 slov)
- Pouzity ton a paleta

```
Ktery koncept vygenerovat? (A/B/C nebo vlastni prompt)
```

### 6. Validuj pred generovanim (Thumbnail Test)

Pred odeslanim na generovani zkontroluj prompt:
- ✅ Ma jasny hlavni subjekt? (min 40% plochy)
- ✅ Bude rozpoznatelny ve 100×67px thumbnails?
- ✅ Za 0.5s bude jasne, o cem obrazek je?
- ✅ Je prostor pro titulek? (negativni prostor)
- ✅ Odpovida ton a paleta clanku?

Pokud ne, uprav prompt.

### 7. Generuj obrazek

Po potvrzeni spust:

```python
import sys
sys.path.insert(0, "C:/Users/stock/Documents/000_NGM/NG-ROBOT")
from image_generator import ImageGenerator
from pathlib import Path

gen = ImageGenerator()
article_dir = Path("C:/Users/stock/Documents/000_NGM/NG-ROBOT/processed/FOLDER")

result = gen.generate_from_prompt(
    prompt="ZVOLENY_PROMPT",
    save_dir=article_dir / "images",
    aspect_ratio="ASPECT",        # 3:2 pro hero, 16:9 pro ilustrace, 4:3 pro infografiku
    image_type="TYP",             # hero / illustration / infographic
    no_text=True,                 # vzdy True krome infografik
)

if result.success:
    print(f"Vygenerovano: {result.filename}")
    print(f"Cesta: {result.filepath}")
else:
    print(f"Chyba: {result.error}")
```

### 8. Informuj o QA

Po uspesnem generovani upozorni:
```
Obrazek vygenerovan s qa_status=pending.
Schvalte ho v galerii clanku ve web UI (http://localhost:5001).
```

## Dulezite

- Obrazky se ukladaji do `processed/SLUG/images/`
- Metadata se zapisuji do `images/captions.json` automaticky
- Novy obrazek ma `qa_status: "pending"` — musi byt schvalen v galerii
- Pro hero image pouzij `setHeroImage()` v galerii po schvaleni
- Styl se prebira z `custom_styles.json` nebo built-in STYLES v image_generator.py
- Visual brief z faze 0 je PREFEROVANY zdroj — manualni analyza jen jako fallback
