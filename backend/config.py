"""Konfigurace aplikace NGM Localizer."""

import os
from pathlib import Path

# Zakladni cesty
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PROJECTS_DIR = DATA_DIR / "projects"
EXPORTS_DIR = DATA_DIR / "exports"
UPLOADS_DIR = DATA_DIR / "uploads"
TRANSLATION_MEMORY_PATH = DATA_DIR / "translation_memory.json"

# Terminologická databáze (ngm-terminology v2.0)
# Multi-doménová referenční DB — 244K+ termínů (geografie, geologie, medicína, ...)
# Override přes env var TERMDB_PATH pro jiný stroj
MULTI_DOMAIN_DB_PATH = os.environ.get(
    "TERMDB_PATH", r"C:\Users\stock\Documents\000_NGM\BIOLIB\termdb.db"
)

# Claude API — model a token limity pro překlad
TRANSLATION_MODEL = os.environ.get("TRANSLATION_MODEL", "claude-sonnet-4-6")
TRANSLATION_MAX_TOKENS = int(os.environ.get("TRANSLATION_MAX_TOKENS", "8192"))

# Illustrator proxy
PROXY_URL = "http://localhost:3001"
PROXY_TIMEOUT = 60  # sekundy

# Server
HOST = "127.0.0.1"
PORT = 8100

# Zajistit existenci adresaru
for d in [PROJECTS_DIR, EXPORTS_DIR, UPLOADS_DIR]:
    d.mkdir(parents=True, exist_ok=True)
