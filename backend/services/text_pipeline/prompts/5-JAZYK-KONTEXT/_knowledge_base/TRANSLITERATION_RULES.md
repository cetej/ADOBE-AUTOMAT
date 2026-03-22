# TRANSLITERATION_RULES - Pravidla transliterace pro URL a identifikátory

**Verze:** 1.0  
**Účel:** Správný převod české diakritiky pro URL slugy, názvy souborů a identifikátory

---

## 🎯 ZÁKLADNÍ PRAVIDLO

Transliterace = nahrazení znaků s diakritikou jejich ASCII ekvivalenty.

**KRITICKÉ:** Transliterace NENÍ fonetický přepis!

---

## 📋 KOMPLETNÍ TABULKA TRANSLITERACE

### Samohlásky

| Znak | Transliterace | ❌ Chybně | Příklad |
|------|---------------|-----------|---------|
| á | a | - | stát → stat |
| é | e | - | léto → leto |
| **ě** | **e** | ~~i~~ | věk → v**e**k, NE ~~vik~~ |
| í | i | - | bílý → bily |
| ó | o | - | móda → moda |
| ú | u | - | úhel → uhel |
| ů | u | - | dům → dum |
| ý | y | - | starý → stary |

### Souhlásky

| Znak | Transliterace | Příklad |
|------|---------------|---------|
| č | c | český → cesky |
| ď | d | ďábel → dabel |
| ň | n | koň → kon |
| ř | r | řeka → reka |
| š | s | škola → skola |
| ť | t | chuť → chut |
| ž | z | život → zivot |

---

## ⚠️ KRITICKÁ CHYBA: ě → e, NE i!

Nejčastější chyba je záměna `ě` za `i`:

| Slovo | ✅ Správně | ❌ Chybně |
|-------|------------|-----------|
| pravěký | prav**e**ky | ~~prav**i**ky~~ |
| starověký | starov**e**ky | ~~starov**i**ky~~ |
| věk | v**e**k | ~~v**i**k~~ |
| člověk | clov**e**k | ~~clov**i**k~~ |
| věda | v**e**da | ~~v**i**da~~ |
| světlo | sv**e**tlo | ~~sv**i**tlo~~ |
| svět | sv**e**t | ~~sv**i**t~~ |
| město | m**e**sto | ~~m**i**sto~~ |
| tělo | t**e**lo | ~~t**i**lo~~ |
| děti | d**e**ti | ~~d**i**ti~~ |

**Proč k této chybě dochází?**
- `ě` se vyslovuje jako [je] nebo změkčuje předchozí souhlásku
- Ale v písmu je to varianta `e`, NE `i`
- Transliterace pracuje s **grafémem**, ne s **fonémem**

---

## 📝 PRAVIDLA PRO URL SLUGY

### Povolené znaky
- Malá písmena: `a-z`
- Číslice: `0-9`
- Pomlčka: `-`

### Zakázané znaky
- Mezery → nahradit `-`
- Velká písmena → převést na malá
- Speciální znaky → odstranit
- Diakritika → transliterovat
- Podtržítka → nahradit `-`

### Algoritmus

```python
def create_slug(text):
    # 1. Převod na lowercase
    slug = text.lower()
    
    # 2. Transliterace (POZOR na ě!)
    trans = {
        'á': 'a', 'č': 'c', 'ď': 'd', 'é': 'e', 
        'ě': 'e',  # NE 'i'!
        'í': 'i', 'ň': 'n', 'ó': 'o', 'ř': 'r', 
        'š': 's', 'ť': 't', 'ú': 'u', 'ů': 'u', 
        'ý': 'y', 'ž': 'z'
    }
    for cz, ascii in trans.items():
        slug = slug.replace(cz, ascii)
    
    # 3. Mezery → pomlčky
    slug = slug.replace(' ', '-')
    
    # 4. Odstranění speciálních znaků
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    
    # 5. Odstranění duplicitních pomlček
    slug = re.sub(r'-+', '-', slug)
    
    # 6. Odstranění pomlček na začátku/konci
    slug = slug.strip('-')
    
    return slug
```

### Příklady

| Originál | ✅ Správně | ❌ Chybně |
|----------|------------|-----------|
| Pravěký člověk z Maroka | praveky-clovek-z-maroka | ~~praviky-clovik-z-maroka~~ |
| Věda a výzkum | veda-a-vyzkum | ~~vida-a-vyzkum~~ |
| České dějiny | ceske-dejiny | ~~ceski-dijiny~~ |
| Městský život | mestsky-zivot | ~~mistsky-zivot~~ |
| Děti a škola | deti-a-skola | ~~diti-a-skola~~ |

---

## 📁 PRAVIDLA PRO NÁZVY SOUBORŮ

### Doporučení
- Používat pouze ASCII znaky
- Mezery nahradit `_` nebo `-`
- Vyhýbat se speciálním znakům
- Max délka: závisí na systému (255 znaků bezpečně)

### Příklady

| Originál | Název souboru |
|----------|---------------|
| Článek o pravěké čelisti | clanek-o-praveke-celisti.md |
| Vědecká studie 2024 | vedecka-studie-2024.pdf |
| Fotografie č. 1 | fotografie-c-1.jpg |

---

## 🌐 SPECIÁLNÍ PŘÍPADY

### Vlastní jména

U vlastních jmen se transliterace **nepoužívá** v textu, ale ANO v URL:

| Jméno | V textu | V URL |
|-------|---------|-------|
| Jiří Novák | Jiří Novák | jiri-novak |
| Plzeň | Plzeň | plzen |
| České Budějovice | České Budějovice | ceske-budejovice |

### Cizojazyčné názvy s diakritikou

| Originál | V URL |
|----------|-------|
| Grotte à Hominidés | grotte-a-hominides |
| São Paulo | sao-paulo |
| Zürich | zurich |

---

## ✅ KONTROLNÍ CHECKLIST

- [ ] Je `ě` převedeno na `e` (NE na `i`)?
- [ ] Jsou všechny diakritické znaky transliterovány?
- [ ] Jsou mezery nahrazeny pomlčkami?
- [ ] Jsou odstraněny speciální znaky?
- [ ] Je slug celý lowercase?
- [ ] Nejsou na začátku/konci pomlčky?
- [ ] Nejsou duplicitní pomlčky?

---

## 🔧 TESTOVACÍ PŘÍKLADY

Ověř správnost transliterace na těchto slovech:

| Slovo | Očekávaný výstup |
|-------|------------------|
| vědecký | vedecky |
| člověk | clovek |
| pravěký | praveky |
| dějiny | dejiny |
| příroda | priroda |
| životní | zivotni |
| městský | mestsky |
| výzkum | vyzkum |
| žádný | zadny |
| říkat | rikat |

---

**Verze:** 1.0  
**Poslední aktualizace:** 08.01.2026
