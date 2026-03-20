"""Konfigurace aplikace NGM Localizer."""

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
MULTI_DOMAIN_DB_PATH = r"C:\Users\stock\Documents\000_NGM\BIOLIB\termdb.db"

# Illustrator proxy
PROXY_URL = "http://localhost:3001"
PROXY_TIMEOUT = 60  # sekundy

# Server
HOST = "127.0.0.1"
PORT = 8100

# Zajistit existenci adresaru
for d in [PROJECTS_DIR, EXPORTS_DIR, UPLOADS_DIR]:
    d.mkdir(parents=True, exist_ok=True)
