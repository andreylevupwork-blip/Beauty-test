from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


env_file = BASE_DIR / ".env"
if env_file.exists():
    load_dotenv(env_file, override=True)
else:
    load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_chat_id: int | None
    mode: str

    webhook_base_url: str | None
    webhook_path: str
    webhook_host: str
    webhook_port: int

    tz_override: str | None

    content: dict[str, Any]

    @staticmethod
    def load() -> "Settings":
        content = _load_json(DATA_DIR / "content.json")

        bot_token = os.getenv("BOT_TOKEN", "").strip()
        if not bot_token:
            raise RuntimeError(
                "Не задан BOT_TOKEN. Создай файл bot/.env по примеру bot/.env.example"
            )

        admin_chat_id_raw = os.getenv("BOT_ADMIN_CHAT_ID", "").strip()
        admin_chat_id = int(admin_chat_id_raw) if admin_chat_id_raw else None

        mode = os.getenv("MODE", "polling").strip().lower()

        webhook_base_url = os.getenv("WEBHOOK_BASE_URL", "").strip() or None
        webhook_path = os.getenv("WEBHOOK_PATH", "/tg-bot").strip()
        webhook_host = os.getenv("WEBHOOK_HOST", "0.0.0.0").strip()
        webhook_port = int(os.getenv("WEBHOOK_PORT", "8443").strip())

        tz_override = os.getenv("TZ_OVERRIDE", "").strip() or None

        return Settings(
            bot_token=bot_token,
            admin_chat_id=admin_chat_id,
            mode=mode,
            webhook_base_url=webhook_base_url,
            webhook_path=webhook_path,
            webhook_host=webhook_host,
            webhook_port=webhook_port,
            tz_override=tz_override,
            content=content,
        )


settings = Settings.load()

