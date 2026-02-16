from typing import Literal

from amrita_core.hook.event import (
    Event,
)
from nonebot.adapters.onebot.v11 import (
    GroupMessageEvent,
    MessageEvent,
    PokeNotifyEvent,
)


class UniPokeEvent(Event):
    nb_event: PokeNotifyEvent

    def get_event_on_location(self) -> Literal["group", "private"]:
        return (
            "group"
            if getattr(self.nb_event, "group_id", None) is not None
            else "private"
        )

    def get_nb_event(self) -> PokeNotifyEvent:
        return self.nb_event


class UniChatEvent(Event):
    nb_event: MessageEvent

    def get_event_on_location(self) -> Literal["group", "private"]:
        return "group" if isinstance(self.nb_event, GroupMessageEvent) else "private"

    def get_nb_event(self) -> MessageEvent:
        return self.nb_event
