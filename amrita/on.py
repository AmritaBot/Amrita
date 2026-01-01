# TODO: 完善
from typing import Literal

from nonebot import on_command as _nb_on_command
from nonebot.matcher import Matcher
from nonebot.permission import Permission
from nonebot.rule import Rule
from nonebot.typing import T_RuleChecker

from amrita.plugins.perm.API.rules import (
    GroupPermissionChecker,
    PermissionChecker,
    UserPermissionChecker,
)

PERMISSION_MODE = Literal[
    "group", "user", "union"
]  # group: 仅检查群是否持有；user: 仅检查用户是否持有；union: 检查群或用户是否持有（任一）


def _wrap_permission_checker(
    checker: type[PermissionChecker], permissions: tuple[str, ...] | str
) -> Permission:
    if isinstance(permissions, str):
        permissions = (permissions,)
    return Permission(*(checker(permission).checker() for permission in permissions))


class OnAmritaWrapper:
    permission: str | tuple[str, ...]
    permission_mode: PERMISSION_MODE

    def __init__(
        self, permission: str | tuple[str, ...], permission_mode: PERMISSION_MODE
    ):
        self.permission = permission
        self.permission_mode = permission_mode

    def on_command(
        self,
        cmd: str | tuple[str, ...],
        rule: Rule | T_RuleChecker | None = None,
        aliases: set[str | tuple[str, ...]] | None = None,
        force_whitespace: str | bool | None = None,
        _depth: int = 0,
        **kwargs,
    ) -> type[Matcher]:
        """注册一个消息事件响应器，并且当消息以指定命令开头时响应。请参考NoneBot的on_command函数参数说明。

        参数:
            cmd: 指定命令内容
            rule: 事件响应规则
            aliases: 命令别名
            force_whitespace: 是否强制命令后必须有指定空白符
            permission: 事件响应权限
            handlers: 事件处理函数列表
            temp: 是否为临时事件响应器（仅执行一次）
            expire_time: 事件响应器最终有效时间点，过时即被删除
            priority: 事件响应器优先级
            block: 是否阻止事件向更低优先级传递
            state: 默认 state
        """
        match self.permission_mode:
            case "group":
                permission_checker = _wrap_permission_checker(
                    GroupPermissionChecker, self.permission
                )
            case "user":
                permission_checker = _wrap_permission_checker(
                    UserPermissionChecker, self.permission
                )
            case "union":
                permission_checker = _wrap_permission_checker(
                    UserPermissionChecker, self.permission
                ) | _wrap_permission_checker(GroupPermissionChecker, self.permission)
        if (kw_perm := kwargs.get("permission")) is not None:
            permission_checker = kw_perm | permission_checker
        kwargs["permission"] = permission_checker
        kwargs["_depth"] = _depth + 1
        return _nb_on_command(
            cmd,
            rule=rule,
            aliases=aliases,
            force_whitespace=force_whitespace,
            **kwargs,
        )


def on_amrita(
    *, permission: str | tuple[str, ...] = (), permission_mode: PERMISSION_MODE = "user"
) -> OnAmritaWrapper:
    return OnAmritaWrapper(permission, permission_mode)
