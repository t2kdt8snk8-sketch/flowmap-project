from __future__ import annotations

import asyncio
import uuid

from loguru import logger
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.message_formatter import format_for_telegram, split_long_message
from core.models import TaskRequest
from core.orchestrator import run_workflow
from storage.output_store import save_result

_HELP_TEXT = (
    "*Content Automation Bot*\n\n"
    "Send me any content request and I'll generate it using multiple AI agents.\n\n"
    "*Examples:*\n"
    "- make a trending Instagram carousel about neo-soul music\n"
    "- write a YouTube script about K-hip-hop history\n"
    "- write Instagram captions in Korean about summer fashion\n"
    "- generate Midjourney prompts for a jazz album cover\n\n"
    "*Commands:*\n"
    "/start — show this message\n"
    "/help — show this message"
)


class ContentAutomationBot:
    def __init__(self, token: str, allowed_user_id: str | None = None) -> None:
        self.token = token
        self.allowed_user_id = allowed_user_id
        self.app = Application.builder().token(token).build()
        self._register_handlers()

    def _register_handlers(self) -> None:
        self.app.add_handler(CommandHandler("start", self._on_start))
        self.app.add_handler(CommandHandler("help", self._on_help))
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_message)
        )

    async def _on_start(
        self, update: Update, ctx: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.message:
            await update.message.reply_text(_HELP_TEXT, parse_mode=ParseMode.MARKDOWN)

    async def _on_help(
        self, update: Update, ctx: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.message:
            await update.message.reply_text(_HELP_TEXT, parse_mode=ParseMode.MARKDOWN)

    async def _on_message(
        self, update: Update, ctx: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not update.message or not update.effective_user:
            return

        user_id = str(update.effective_user.id)
        chat_id = str(update.effective_chat.id) if update.effective_chat else user_id

        # Authorization check
        if self.allowed_user_id and user_id != self.allowed_user_id:
            logger.warning(f"Unauthorized access attempt from user_id={user_id}")
            return

        user_text = update.message.text or ""
        if not user_text.strip():
            return

        task_id = str(uuid.uuid4())

        # Acknowledge immediately — LLM calls take 30-90 seconds
        status_msg = await update.message.reply_text(
            "Processing your request... (30-90 seconds)"
        )

        try:
            request = TaskRequest(
                task_id=task_id,
                user_message=user_text,
                chat_id=chat_id,
            )

            logger.info(f"[{task_id}] Request from {user_id}: {user_text[:80]}")
            workflow_run = await run_workflow(request)

            output_path = await save_result(workflow_run)
            logger.info(f"[{task_id}] Saved to {output_path}")

            if workflow_run.final_output:
                response_text = format_for_telegram(workflow_run.final_output)
                chunks = split_long_message(response_text, max_length=4000)

                # Delete the "processing..." message
                await status_msg.delete()

                for chunk in chunks:
                    try:
                        await update.message.reply_text(
                            chunk, parse_mode=ParseMode.MARKDOWN
                        )
                    except Exception:
                        # Fallback: send without markdown if formatting fails
                        await update.message.reply_text(chunk)
            else:
                await status_msg.edit_text(
                    "Failed to generate content. Please try again with a different request."
                )

        except Exception as e:
            logger.error(f"[{task_id}] Unhandled error: {e}", exc_info=True)
            try:
                await status_msg.edit_text(
                    f"An error occurred: {str(e)[:200]}\n\nPlease try again."
                )
            except Exception:
                pass

    async def run(self) -> None:
        """Initialize and start polling for Telegram messages."""
        await self.app.initialize()
        await self.app.start()
        assert self.app.updater is not None
        await self.app.updater.start_polling(drop_pending_updates=True)
        logger.info("Telegram bot started, polling for messages...")
        try:
            # asyncio.gather와 함께 돌 때 — 취소될 때까지 대기
            await asyncio.Event().wait()
        finally:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
