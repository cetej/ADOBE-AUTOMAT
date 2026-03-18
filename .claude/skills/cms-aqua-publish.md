---
name: cms-aqua-publish
description: "Publikování zpracovaného článku do CMS Aqua jako KONCEPT. Použij VŽDY když uživatel říká 'publikovat', 'publish', 'CMS', 'Aqua', 'zadat do CMS', 'nahrát článek', nebo chce poslat článek do redakčního systému. Skill pokrývá celý 7-krokový workflow: autentizace, upload obrázků do DAM, vytvoření článku, infoboxy, inline obrázky, galerie, videa. NEPOUŽÍVEJ pro diagnostiku CMS problémů (použij cms_aqua_diag.py) ani pro obecnou práci s API."
---

# CMS Aqua Publish — workflow pro publikování článku

Tento skill orchestruje publikování zpracovaného NG-ROBOT článku do CMS Aqua jako KONCEPT. Celý proces trvá 10-30 sekund místo 20-30 min ručního zadání.

## Prerekvizity

- Článek musí mít `9_final.md` (dokončený pipeline)
- `images/captions.json` musí existovat (mapování obrázků)
- `.aqua_refresh_token` musí existovat (autentizace)

## Spuštění

```bash
# CLI
python cms_aqua_publisher.py "processed/YYYY-MM-DD_nazev-clanku"

# Web API
POST /api/article/publish-aqua  {"path": "processed/..."}

# Web UI — tlačítko "CMS Aqua" v detailu článku
```

## 7-krokový workflow (publish_to_aqua)

### 1. Autentizace
- Refresh token z `.aqua_refresh_token` → Bearer JWT
- SSO endpoint: `sso.production.vlm.nmheagle.sk/connect/token`
- Token se cachuje v `.aqua_token`

### 2. Upload obrázků do DAM
Pro každý obrázek v `images/`:
1. **DAM upload** — `POST dam.production.vlm.nmheagle.sk/api/Image` (multipart)
2. **DAM metadata update** — `PUT /api/Image/metadata` s `entityUuid` + IPTC metadata
3. **CMS Image vytvoření** — `POST /Image` s `UseBasicCrops: True` + `DamBasicCropDims`

**Kritické:**
- `usage_type` enum: `article_hero`, `article_gallery`, `article_body_block` (NIKDY `article_body` — vrací 400)
- **NIKDY nevolat `set-in-review` s `inReview=True`** — zamyká obrázky v CMS editoru
- DamBasicCropDims formát: `[{"Dim": "1366x910", "Set": "3:2"}, ...]` — PascalCase stringy

### 3. Vytvoření článku
- `POST /Article/create` s titulkem + rubrikou + site ID 209
- Rubrika: metadata.json → `RUBRIC_TO_AQUA_CATEGORY` mapování

### 4. Infoboxy (📦 Infobox, 📚 Glosář, FAQ)
1. `POST /Infobox` — vytvoří entitu (bez image!)
2. `PUT /Infobox/{id}` — **retouch s image** (payload MUSÍ obsahovat `"id"`)
3. Přidat `infoBoxBlock` do `bodyBlocks`

**Pořadí je kritické:** Retouch PŘED `PUT /Article` — jinak `embedded.infobox.image` zůstane null.

### 5. Body blocks + inline obrázky
1. `POST /ArticleBodyConverter/articleFieldToBlocksConversion` — HTML → blocks
2. Najít `[Popisek: ...]` markery → spárovat s captions.json → vytvořit imageBlock
3. Interleaving imageBlocks + infoBoxBlocks do bodyBlocks na správné pozice

### 6. PUT Article (overlay pattern)
1. `GET /Article/{id}` → aktuální stav
2. Overlay: heroImage, bodyBlocks, summary (V KOSTCE), perex, SEO metadata
3. `PUT /Article/{id}` s kompletním payloadem

**V KOSTCE → `article.summary`** (ne infobox!): markdown tabulka → `<ul><li><strong>emoji</strong> text</li></ul>`

### 7. Videa (volitelné)
1. `POST /Video` s metadata z captions.json + délka přes ffprobe
2. Video entity se vytvoří se `status: "new"` — MP4 nutno nahrát ručně do Livebox CDN

### 8. Tracking
- Záznam do `.cms_published.json` (article_id, timestamp, path)

## Known gotchas

| Problém | Řešení |
|---------|--------|
| `PUT /Image/{uuid}` vrací 405 | Metadata update POUZE přes `/Image/metadata` |
| `POST /Infobox` ignoruje `image` | Nutný retouch: `PUT /Infobox/{id}` s image |
| `inReview=True` zamyká obrázky | NIKDY nenastavovat — default `false` je správný |
| `mediaRatioUsages` prázdné | S `UseBasicCrops=true` se ignoruje — to je OK |
| Inbox články nemají pozice obrázků | Chybí `<!--IMAGE_PLACEHOLDER-->` markery |
| `article_body` usage_type | Neexistuje — použít `article_body_block` |

## Diagnostika problémů

Pokud publish selže, spusť diagnostiku:
```bash
python cms_aqua_diag.py
```

Pro opravení zamčených obrázků (inReview=True):
```bash
# V cms_aqua_publisher.py: _dam_set_in_review() s inReview=False
PUT /api/Image/set-in-review  {"inReview": false, "imageUuids": ["uuid1", ...]}
```
