from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SessionTemp(BaseModel):
    message_id: int
    timestamp: datetime = Field(default_factory=datetime.now)


@dataclass
class ChatManager:
    debug: bool = False
    session_clear_group: dict[str, SessionTemp] = field(default_factory=dict)
    session_clear_user: dict[str, SessionTemp] = field(default_factory=dict)
    custom_menu: list[dict[str, str]] = field(default_factory=list)
    running_messages_poke: dict[str, Any] = field(default_factory=dict)


chat_manager = ChatManager()
