# Session Checkpoint

## Next Session: Layout Generator — Multi-Article Maps Support

**Priority**: medium
**Prepared**: 2026-03-23
**Context**: Quality audit odhalil design gap — `build_from_multi_article_plans()` nemá `maps_dir` parametr

### Zadání

Přidej podporu map (MAP_ART override) do multi-article IDML buildů.

### Co je hotové
- `build_from_plan()` má plnou maps podporu (`maps_dir` param + `resolve_image_with_maps()`)
- `build_from_multi_article_plans()` už detekuje `FrameType.MAP_ART` sloty (opraveno v auditu)
- Router `layout.py` předává `maps_dir` pro single-article build (L508-515) i batch (L1221-1228)
- Multi-article router (`run_multi_generate()` L1698) volá `build_from_multi_article_plans()` BEZ maps_dir

### Co zbývá udělat

1. **`idml_builder.py`** — přidat `article_maps_dirs: dict[str, Path] | None = None` parametr do `build_from_multi_article_plans()`:
   - Signatura: `{article_id: maps_dir_path}`
   - V image_map loop: pro každý article načíst jeho maps_dir a volat `resolve_image_with_maps()`
   - Extrahovat image_map building do helperu `_build_image_map()` (eliminuje poslední duplikát mezi single a multi)

2. **`routers/layout.py`** — v `run_multi_generate()` (L1698+):
   - Sestavit `article_maps_dirs` dict z project dirs
   - Předat do `build_from_multi_article_plans()`

3. **Test**: Vytvořit multi-article projekt s mapami a ověřit, že maps override funguje

### Klíčové soubory
- `backend/services/layout/idml_builder.py` — L1209-1282 (build_from_multi_article_plans)
- `backend/services/layout/idml_builder.py` — L1138-1206 (build_from_plan — reference)
- `backend/routers/layout.py` — L1698-1760 (run_multi_generate)
- `backend/services/layout/illustrator_exporter.py` — resolve_image_with_maps()

### Pravidla
- NIKDY `ElementTree.write()` — string replace + `ET.fromstring()` validace
- Importy: `from models_layout import ...` (bez `backend.` prefixu)
- Tier: light (1 soubor hlavní změna + 1 router update)
