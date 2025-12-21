"""
A simple plugin that bridges Telegram <-> Amrita.

This plugin is intentionally minimal: it demonstrates how to start the TelegramAdapter
and register a handler. By default it echoes messages. Replace the `message_handler`
function with integration code that sends text to Amrita's chat processing function
(e.g. call into the chat manager / conversation manager inside Amrita) and returns the reply.

Usage:
- Set environment variable TELEGRAM_BOT_TOKEN
- Ensure python-telegram-bot>=20.0 is installed
- Run Amrita as usual; this plugin will start the background polling adapter.

Integration hint:
- If Amrita exposes an async function to process inbound messages (for example
  amrita.plugins.chat.handle_incoming_message(user_id, text, meta)), call that here and
  return the reply.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Optional

from amrita.adapters.telegram_adapter import TelegramAdapter

logger = logging.getLogger(__name__)

_adapter: Optional[TelegramAdapter] = None


async def message_handler(user_id: str, text: str, meta: Any) -> Optional[str]:
    """
    Example handler.
    Replace this with a call into Amrita's chat handling subsystem.

    Example (pseudo):
        from amrita.plugins.chat import chat_manager
        reply = await chat_manager.handle_text(user_id, text, meta)
        return reply
    """
    # Simple echo for demonstration
    logger.debug("Received from Telegram user %s: %s", user_id, text)
    return f"Echo: {text}"


def setup_telegram_adapter(token: Optional[str] = None) -> None:
    global _adapter
    if _adapter is not None:
        return
    token = token or os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN env var is not set; Telegram adapter disabled.")
        return
    _adapter = TelegramAdapter(token=token)
    _adapter.register_handler(message_handler)
    # start polling in background
    _adapter.start()
    logger.info("Telegram adapter started (polling).")


# Optional: auto-start when the module is imported (only do this if you want auto-run)
if os.getenv("AMRITA_TELEGRAM_AUTO_START", "1") == "1":
    try:
        # If Amrita runs inside an asyncio loop, starting here is safe because adapter runs
        # its own background thread. Keep startup idempotent.
        setup_telegram_adapter()
    except Exception as e:
        logger.exception("Failed to start Telegram adapter: %s", e)
