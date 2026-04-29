"""Audit vsech MAP projektu na 5 typu chyb v prekladech.

Heuristika:
  CAPS — popisek zacina velkym pismenem (krome vlastnich jmen / vet)
  CYR — cyrilice v ceskem prekladu
  GENERIC — anglicke generikum (Highway, Lake, Sound) v ceskem vystupu
  IDIOM_INTEREST — "zajmu" jako preklad "of interest"
  HLUBINNY_OOC — "hlubinny" mimo kontext sesuvu
  INCONSISTENT — stejny EN, ruzne CZ ve stejnem projektu
"""
import sys
import json
from pathlib import Path
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

projects_dir = Path(r"C:\Users\stock\Documents\000_NGM\ADOBE-AUTOMAT\data\projects")
all_files = sorted(projects_dir.glob("*.json"))

maps = []
for f in all_files:
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("type") == "map" and any(e.get("czech") for e in d.get("elements", [])):
            translated = sum(1 for e in d["elements"] if e.get("czech"))
            maps.append((f, d, translated))
    except Exception:
        continue

print(f"MAP projektu s preklady: {len(maps)}\n")

PROPER_NAMES = {
    "Aljaška", "Aljašská", "Aljašské", "Aljašský",
    "Pacific", "Tichý", "Atlantský", "Atlantic", "Severní", "Arctic",
    "America", "Amerika", "Severoamerická", "Jižní", "Asie", "Evropa", "Afrika",
    "NORTH", "SOUTH", "EAST", "WEST",
    "LEGEND", "KEY", "Legenda",
}

GENERIC_LOWERCASE = {
    "jezero", "záliv", "zátoka", "pohoří", "hory", "průliv", "průplav",
    "dálnice", "silnice", "mys", "ostrov", "ledovec", "řeka", "potok",
    "oceán", "moře", "hora", "údolí", "sedlo", "průsmyk", "park",
    "národní", "republiky",
    "aktivní", "tající", "starší", "hlubinný", "mělký", "nový", "staré",
    "směr", "počátek", "konec", "začátek",
    "provoz", "trasa", "trasy", "čas", "doba", "množství", "počet",
    "jiný", "jiná", "jiné", "další", "ostatní", "každý", "některé",
    "celý", "celá", "celé", "průměrný", "celkem", "celkový",
    "horní", "dolní", "spodní", "vrchní", "východní", "západní",
    "centrální", "centrum", "okrajový", "vnitřní", "vnější",
    "letní", "zimní", "jarní", "podzimní",
    "trasy", "popis", "vysvětlivky",
}

ALL_PROBLEMS = []

for f, d, n_translated in maps:
    pid = f.stem
    en_to_cz = defaultdict(list)
    for e in d["elements"]:
        if e.get("contents") and e.get("czech"):
            en_to_cz[e["contents"].strip()].append((e["id"], e["czech"]))

    for e in d["elements"]:
        cz = (e.get("czech") or "").strip()
        en = (e.get("contents") or "").strip()
        if not cz:
            continue

        # A) Kapitalizace popisku
        # Heuristika s filtrem na vlastni geo jmena typu "Aralske jezero":
        # - "X-ske/cke + singular generikum" → vlastni jmeno, OK velke
        # - "Adj + plural / abstract noun" → popisek, ma byt male
        first_chunk = cz.split("\n")[0].strip()
        flat_cz = cz.replace("\n", " ").replace("\r", " ").strip()
        words = flat_cz.split() if flat_cz else []
        if words:
            first_word = words[0]
            second_word = words[1] if len(words) > 1 else ""
            if first_word and first_word[0].isalpha() and first_word[0].isupper():
                if cz.isupper():
                    pass  # ALL CAPS layout
                elif cz.rstrip(")").endswith("."):
                    pass  # sentence
                elif first_word in PROPER_NAMES:
                    pass
                else:
                    fl = first_word.lower()
                    sl = second_word.lower().rstrip(",.;:")
                    is_adj = fl.endswith(("ý", "á", "é", "í"))
                    is_generic = fl in GENERIC_LOWERCASE
                    # Singular generika ktera tvori vlastni jmena geo objektu
                    SINGULAR_PROPER_GENERICS = {
                        "jezero", "moře", "oceán", "záliv", "mys", "ostrov",
                        "pohoří", "údolí", "sedlo", "průsmyk", "průliv", "průplav",
                        "ledovec", "park", "rezervace", "civilizace", "říše",
                        "říše", "doba", "epocha", "království", "republika",
                        "pruh", "hřbet", "kotlina", "plošina", "polární",
                        "polostrov", "poloostrov", "dálnice", "silnice",
                        "stát", "město", "vesnice",
                    }
                    # Pokud second slovo je proper-generikum singular → vlastni jmeno
                    second_is_proper_generic = sl in SINGULAR_PROPER_GENERICS
                    # "hory" je generikum kdyz prvni slovo je etnonymum/region (Aljaška, Skalisté)
                    if sl == "hory" and is_adj:
                        second_is_proper_generic = True

                    if (is_generic or is_adj) and not second_is_proper_generic:
                        ALL_PROBLEMS.append({
                            "project": pid,
                            "type": "CAPS",
                            "id": e["id"],
                            "en": en,
                            "cz": cz,
                        })

        # B) Cyrilice
        cyr = [c for c in cz if 0x0400 <= ord(c) <= 0x04FF]
        if cyr:
            ALL_PROBLEMS.append({
                "project": pid, "type": "CYR", "id": e["id"],
                "en": en, "cz": cz, "chars": cyr,
            })

        # C) Anglicke generikum v ceskem vystupu
        for gen in ["Highway", "Hwy", "Sound", "Lake", "Bay",
                    "Mountains", "Range", "River", "Passage", "Canal",
                    "Glacier", "Island", "Cape", "Peninsula", "Falls",
                    "Strait", "Valley", "Plateau"]:
            # Specifika: "Arm" je problematic (zaroven anglicke ale i mass noun)
            if gen in en and gen in cz:
                ALL_PROBLEMS.append({
                    "project": pid, "type": "GENERIC", "id": e["id"],
                    "en": en, "cz": cz, "gen": gen,
                })
                break

        # D) "zajmu" idiom
        if ("zájmu" in cz.lower() or "zájem" in cz.lower()) and "interest" in en.lower():
            ALL_PROBLEMS.append({
                "project": pid, "type": "IDIOM_INTEREST",
                "id": e["id"], "en": en, "cz": cz,
            })

    # E) Nekonzistence
    for en_text, vars_ in en_to_cz.items():
        unique_cz = set(v[1] for v in vars_)
        if len(unique_cz) > 1 and len(en_text) >= 3:
            normalized = set(c.lower().strip().replace("\n", " ").replace("  ", " ") for c in unique_cz)
            if len(normalized) > 1:
                for elem_id, cz_var in vars_:
                    ALL_PROBLEMS.append({
                        "project": pid, "type": "INCONSISTENT",
                        "id": elem_id, "en": en_text, "cz": cz_var,
                        "variants": list(unique_cz),
                    })

by_proj = defaultdict(lambda: defaultdict(list))
for p in ALL_PROBLEMS:
    by_proj[p["project"]][p["type"]].append(p)

type_totals = defaultdict(int)
for proj, types in by_proj.items():
    for t, items in types.items():
        type_totals[t] += len(items)

print("=== SUMARIZACE ===")
print(f"  CAPS (kapitalizace popisku):       {type_totals['CAPS']}")
print(f"  CYR (cyrilice):                    {type_totals['CYR']}")
print(f"  GENERIC (anglicke generikum):      {type_totals['GENERIC']}")
print(f"  IDIOM_INTEREST (zajmu):            {type_totals['IDIOM_INTEREST']}")
print(f"  INCONSISTENT (stejny EN, ruzne CZ): {type_totals['INCONSISTENT']}")
print(f"\nPostizeno projektu: {len(by_proj)}/{len(maps)}\n")

for proj in sorted(by_proj.keys()):
    types = by_proj[proj]
    counts = ", ".join(f"{t}={len(v)}" for t, v in sorted(types.items()))
    label = " (uz opraveny)" if proj == "ngm-2605-alaska-v16-final2-fp-metric" else ""
    print(f"--- {proj}{label} ---  {counts}")
    for t, items in sorted(types.items()):
        for p in items[:5]:
            cz_show = p["cz"].replace("\n", "\\n")[:50]
            en_show = p["en"].replace("\n", "\\n")[:50]
            extra = ""
            if t == "GENERIC":
                extra = f' [gen={p["gen"]}]'
            elif t == "CYR":
                extra = f' [chars={p["chars"]}]'
            elif t == "INCONSISTENT":
                vars_disp = [v.replace(chr(10), "\\n") for v in p["variants"][:3]]
                extra = f' [variants={vars_disp}]'
            print(f"  [{t:14s}] {p['id'][:28]:28s}  EN={en_show!r:55s}  CZ={cz_show!r}{extra}")
        if len(items) > 5:
            print(f"  ... a dalsich {len(items)-5} v typu {t}")
    print()
