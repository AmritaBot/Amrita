from .event import EventTypeEnum
from .matcher import Matcher


def on_chat(*, priority: int = 10, block: bool = True):
    return on_event(EventTypeEnum.CHAT, priority, block)


def on_poke(*, priority: int = 10, block: bool = True):
    return on_event(EventTypeEnum.POKE, priority, block)


def on_before_chat(*, priority: int = 10, block: bool = True):
    return on_event(EventTypeEnum.BEFORE_CHAT, priority, block)


def on_before_poke(*, priority: int = 10, block: bool = True):
    return on_event(EventTypeEnum.BEFORE_POKE, priority, block)


def on_event(event_type: EventTypeEnum, priority: int = 10, block: bool = True):
    return Matcher(event_type, priority, block)
