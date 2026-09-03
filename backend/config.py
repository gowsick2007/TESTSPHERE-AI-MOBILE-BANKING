"""
TestSphere AI — Configuration Manager
Loads system config from config.json.
"""
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.json"

with open(CONFIG_PATH, "r") as f:
    CONFIG = json.load(f)

DB_PATH = BASE_DIR / CONFIG["data"]["db_path"]
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
