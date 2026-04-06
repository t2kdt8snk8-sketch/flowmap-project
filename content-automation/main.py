from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import uvicorn
from loguru import logger

from config.settings import get_settings


def _configure_logging(settings) -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}",
    )
    logger.add(
        Path("logs") / "bot.log",
        rotation="10 MB",
        retention="14 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{line} | {message}",
        encoding="utf-8",
    )


async def run_web_server(port: int) -> None:
    from web.app import app
    # uvicorn.Server를 직접 await — uvicorn.run()은 내부에서 새 이벤트루프를 만들어 asyncio.gather와 충돌
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    logger.info(f"Web UI: http://localhost:{port}")
    await server.serve()


async def run_telegram_bot(token: str, allowed_user_id: str | None) -> None:
    from bot.telegram_bot import ContentAutomationBot
    bot = ContentAutomationBot(token=token, allowed_user_id=allowed_user_id)
    logger.info("Telegram bot starting...")
    await bot.run()


async def main() -> None:
    settings = get_settings()
    _configure_logging(settings)

    logger.info("Content Automation starting up")
    logger.info(f"LLM proxy : {settings.llm_base_url}")
    logger.info(f"Web port  : {settings.web_port}")
    logger.info(f"Models    : opus={settings.model_opus} | sonnet={settings.model_sonnet} | haiku={settings.model_haiku}")

    tasks = [run_web_server(port=settings.web_port)]

    if settings.telegram_bot_token:
        tasks.append(run_telegram_bot(
            token=settings.telegram_bot_token,
            allowed_user_id=settings.allowed_telegram_user_id,
        ))
    else:
        logger.warning("TELEGRAM_BOT_TOKEN 없음 — 텔레그램 봇 비활성화")

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
