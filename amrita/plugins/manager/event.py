from typing import TypeAlias

from nonebot.adapters.onebot.v11 import (
    FriendAddNoticeEvent,
    FriendRecallNoticeEvent,
    FriendRequestEvent,
    GroupAdminNoticeEvent,
    GroupBanNoticeEvent,
    GroupDecreaseNoticeEvent,
    GroupIncreaseNoticeEvent,
    GroupMessageEvent,
    GroupRecallNoticeEvent,
    GroupRequestEvent,
    GroupUploadNoticeEvent,
    HonorNotifyEvent,
    MessageEvent,
    NotifyEvent,
    PokeNotifyEvent,
    PrivateMessageEvent,
)

GroupEvent: TypeAlias = (
    GroupAdminNoticeEvent
    | GroupDecreaseNoticeEvent
    | GroupIncreaseNoticeEvent
    | GroupMessageEvent
    | GroupRequestEvent
    | GroupUploadNoticeEvent
    | GroupRecallNoticeEvent
    | GroupBanNoticeEvent
    | HonorNotifyEvent
)

UserIDEvent: TypeAlias = (
    GroupEvent
    | PokeNotifyEvent
    | PrivateMessageEvent
    | NotifyEvent
    | MessageEvent
    | FriendRequestEvent
    | FriendAddNoticeEvent
    | FriendRecallNoticeEvent
)
