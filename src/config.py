import os
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).parent.parent
FEEDS_PATH = BASE_DIR / "config" / "feeds.yaml"
SETTINGS_PATH = BASE_DIR / "config" / "settings.yaml"
SETTINGS_LOCAL_PATH = BASE_DIR / "config" / "settings.local.yaml"


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def read_feeds() -> list[dict]:
    with open(FEEDS_PATH) as f:
        return yaml.safe_load(f).get("feeds", [])


def write_feeds(feeds: list[dict]):
    with open(FEEDS_PATH, "w") as f:
        yaml.dump({"feeds": feeds}, f, allow_unicode=True, default_flow_style=False)


def read_settings() -> dict:
    with open(SETTINGS_PATH) as f:
        settings = yaml.safe_load(f) or {}

    if SETTINGS_LOCAL_PATH.exists():
        with open(SETTINGS_LOCAL_PATH) as f:
            local = yaml.safe_load(f) or {}
        settings = _deep_merge(settings, local)

    env_map = {
        "ANTHROPIC_API_KEY": ("summarizer", "anthropic", "api_key"),
        "ANTHROPIC_BASE_URL": ("summarizer", "anthropic", "base_url"),
        "OPENAI_API_KEY": ("summarizer", "openai", "api_key"),
        "OPENAI_BASE_URL": ("summarizer", "openai", "base_url"),
        "OPENAI_MODEL": ("summarizer", "openai", "model"),
        "ANTHROPIC_MODEL": ("summarizer", "anthropic", "model"),
        "TELEGRAM_BOT_TOKEN": ("push", "telegram", "bot_token"),
        "TELEGRAM_CHAT_ID": ("push", "telegram", "chat_id"),
        "BARK_DEVICE_KEY": ("push", "bark", "device_key"),
        "BARK_SERVER_URL": ("push", "bark", "server_url"),
        "WECOM_WEBHOOK_URL": ("push", "wecom", "webhook_url"),
        "WPS_WEBHOOK_URL": ("push", "wps", "webhook_url"),
        "LARK_WEBHOOK_URL": ("push", "lark", "webhook_url"),
        "LARK_SECRET": ("push", "lark", "secret"),
    }
    for env_key, path in env_map.items():
        val = os.environ.get(env_key)
        if val:
            d = settings
            for k in path[:-1]:
                d = d.setdefault(k, {})
            d[path[-1]] = val

    push_enabled = os.environ.get("PUSH_ENABLED")
    if push_enabled:
        settings.setdefault("push", {})["enabled"] = [
            x.strip() for x in push_enabled.split(",") if x.strip()
        ]

    provider = os.environ.get("SUMMARIZER_PROVIDER")
    if provider:
        settings.setdefault("summarizer", {})["provider"] = provider

    return settings


def write_settings(settings: dict):
    with open(SETTINGS_LOCAL_PATH, "w") as f:
        yaml.dump(settings, f, allow_unicode=True, default_flow_style=False)
