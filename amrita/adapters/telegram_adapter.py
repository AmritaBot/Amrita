"""
Telegram adapter / bridge for Amrita.

This module provides a small, minimal bridge using python-telegram-bot (v20+).
It implements a TelegramAdapter with a simple register_handler(handler) API:

    - handler(user_id: str, text: str, meta) -> str | None | Awaitable[str | None]

The adapter will call the handler when a text message is received and send the handler's
returned text back to the user.

Notes:
- Requires python-telegram-bot>=20.0 (asyncio-based).
- The adapter runs the Bot in polling mode in a background thread to keep integration simple.
- You can replace polling with webhook logic if you prefer.
"""

from __future__ import annotations

import asyncio
import os
import threading
from typing import Any, Awaitable, Callable, Optional, Union

try:
    from telegram import Update
    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        filters,
        ContextTypes,
    )
except Exception as e:  # pragma: no cover - runtime optional import
    Application = None  # type: ignore
    Update = None  # type: ignore
    ContextTypes = None  # type: ignore
    filters = None  # type: ignore
    raise RuntimeError(
        "python-telegram-bot is required for TelegramAdapter. "
        "Install with `pip install python-telegram-bot>=20.0`"
    ) from e


HandlerType = Callable[[str, str, Any], Union[Optional[str], Awaitable[Optional[str]]]]


async def _maybe_await(value):
    if asyncio.iscoroutine(value):
        return await value
    return value


class TelegramAdapter:
    def __init__(self, token: Optional[str] = None, use_polling: bool = True):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.token:
            raise RuntimeError(
                "TELEGRAM_BOT_TOKEN not provided and TELEGRAM_BOT_TOKEN env var not set."
            )
        if Application is None:
            raise RuntimeError("python-telegram-bot is not available.")
        self._app: Application = Application.builder().token(self.token).build()
        self._handler: Optional[HandlerType] = None
        self._use_polling = use_polling
        self._running_thread: Optional[threading.Thread] = None

        # register internal handlers
        self._app.add_handler(CommandHandler("start", self._on_start))
        self._app.add_handler(
            MessageHandler(filters.TEXT & (~filters.COMMAND), self._on_message)
        )

    def register_handler(self, handler: HandlerType) -> None:
        """Register a coroutine or sync function handler(user_id, text, meta) -> reply."""
        self._handler = handler

    async def _on_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Hello! This bot is connected to Amrita.")

    async def _on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text or ""
        user_id = str(update.effective_user.id) if update.effective_user else "unknown"
        meta = {"platform": "telegram", "update": update, "context": context}
        if self._handler:
            try:
                result = await _maybe_await(self._handler(user_id, text, meta))
                if result:
                    await update.message.reply_text(result)
            except Exception as exc:
                # keep adapter resilient; you can enhance logging here
                await update.message.reply_text("Internal error processing your message.")
                raise
        else:
            await update.message.reply_text("No handler registered for messages.")

    def start(self) -> None:
        """Start the adapter in background (polling). This blocks if polling used directly,
        so we run it in a daemon thread to avoid blocking the main process."""
        if not self._use_polling:
            # Implement webhook or async start if desired
            raise NotImplementedError("Only polling mode is implemented in this adapter.")
        if self._running_thread and self._running_thread.is_alive():
            return
        def _run():
            # run_polling is blocking but sets up the event loop required by PTB
            self._app.run_polling()
        t = threading.Thread(target=_run, name="amrita-telegram-adapter", daemon=True)
        t.start()
        self._running_thread = t

    def stop(self) -> None:
        try:
            self._app.stop()
        except Exception:
            pass
        if self._running_thread and self._running_thread.is_alive():
            # thread is daemon; it will stop when program exits
            self._running_thread = None
