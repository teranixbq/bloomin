import json
import os
from core.constants import MSG_WELCOME_DEFAULT, DEFAULT_SYSTEM_PROMPT

CONFIG_PATH = os.getenv("CONFIG_PATH", "./config.json")

DEFAULT_CONFIG = {
    "knowledge":     "",
    "corpus_url":    "",   # legacy: hanya dipakai untuk migrasi satu kali ke "knowledge"
    "owner_phone":   "",
    "is_setup_done": False,
    "brand_name":    "Bloomin",
    "welcome_msg":   MSG_WELCOME_DEFAULT,
    "system_prompt": DEFAULT_SYSTEM_PROMPT,
}

def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            data = json.load(f)
            return {**DEFAULT_CONFIG, **data}
    return DEFAULT_CONFIG.copy()

def save_config(config: dict):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def is_setup_done() -> bool:
    cfg = load_config()
    has_data = bool(cfg.get("knowledge") or cfg.get("corpus_url"))
    return bool(cfg.get("is_setup_done") and has_data and cfg.get("owner_phone"))
