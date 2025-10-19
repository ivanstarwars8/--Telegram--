"""Utility to create a minimal .env file for local runs."""
from __future__ import annotations

import os
from pathlib import Path
from textwrap import dedent


ENV_TEMPLATE = dedent(
    """
    SECRET_KEY={secret_key}
    POSTGRES_DSN=postgresql+asyncpg://focus:focus@postgres:5432/focus
    REDIS_DSN=redis://redis:6379/0
    TELEGRAM_BOT_TOKEN={telegram_token}
    TELEGRAM_ADMIN_IDS=
    CELERY_BROKER_URL=redis://redis:6379/1
    CELERY_RESULT_BACKEND=redis://redis:6379/2
    API_BASE_URL=http://api:8000
    """
).strip()


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    env_path = project_root / ".env"

    if env_path.exists():
        print(".env already exists. Nothing to do.")
        return

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        token = input("Enter Telegram bot token: ").strip()
        if not token:
            raise SystemExit("Telegram bot token is required to bootstrap .env")

    secret = os.getenv("SECRET_KEY", "dev-secret")

    env_content = ENV_TEMPLATE.format(
        telegram_token=token,
        secret_key=secret,
    )

    env_path.write_text(env_content + "\n", encoding="utf-8")
    print(f"Created {env_path.relative_to(project_root)} with default values.")


if __name__ == "__main__":
    main()
