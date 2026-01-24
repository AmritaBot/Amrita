import contextlib
from datetime import datetime

from nonebot.adapters.onebot.v11 import (
    Bot,
    Message,
)
from nonebot.adapters.onebot.v11.event import (
    MessageEvent,
)
from nonebot.matcher import Matcher
from nonebot.params import CommandArg

from amrita.plugins.chat import chatmanager
from amrita.plugins.chat.chatmanager import ChatObject, chat_manager


def get_chat_objects_status(event: MessageEvent) -> dict[str, list[ChatObject]]:
    """获取所有ChatObject的状态分类"""
    running_objects = []
    pending_objects = []
    done_objects = []
    error_objects = []

    all_objects = chat_manager.get_objs(event)

    for obj_meta in all_objects:
        # 通过stream_id找到对应的ChatObject实例
        obj_instance = None
        for obj_list in chat_manager.running_chat_object.values():
            for obj in obj_list:
                if obj.stream_id == obj_meta.stream_id:
                    obj_instance = obj
                    break
            if obj_instance:
                break

        if obj_instance:
            if obj_instance.is_running():
                running_objects.append(obj_instance)
            elif obj_instance.is_waitting():
                pending_objects.append(obj_instance)
            elif obj_instance.get_exception():
                error_objects.append(obj_instance)
            elif obj_instance.is_done():
                done_objects.append(obj_instance)

    return {
        "running": running_objects,
        "pending": pending_objects,
        "done": done_objects,
        "error": error_objects,
    }


def format_chat_object_info(obj: ChatObject) -> str:
    """格式化单个ChatObject的信息"""
    event = obj.event
    user_id = event.user_id
    instance_id, is_group = chatmanager.chat_manager.get_obj_key(event)
    status = "❓ Unknown"
    if obj.is_running():
        status = "🟢 Running"
    elif obj.is_waitting():
        status = "⏳ Pending"
    elif obj.get_exception():
        status = f"❌ Error ({type(obj.get_exception()).__name__})"
    elif obj.is_done():
        status = "✅ Done"

    time_diff = (datetime.now() - obj.last_call).total_seconds()
    time_cost: float = (
        (datetime.now() - obj.end_at).total_seconds() if obj.end_at else 0
    )

    info = (
        f"🆔 ID: {obj.stream_id[:8]}...\n"
        + f"💬 类型: {'👥 群聊' if is_group else '👤 私聊'}\n"
        + f"👤 用户ID: {user_id}\n"
        + f"🔢 实例ID: {instance_id}\n"
        + f">Status: {status}\n"
        + f"⏱️ 最后活动: {time_diff:.0f}s前\n"
        + f"🕐 时间: {obj.time.strftime('%H:%M:%S')}\n"
        + (f"🕐 消耗时间：{time_cost:.0f}s" if time_cost else "")
    )

    return info


async def send_status_report(
    matcher: Matcher, status_dict: dict[str, list[ChatObject]]
) -> None:
    """发送状态报告"""
    report_parts = ["📋【会话运行状态】\n"]

    for status_type, objects in status_dict.items():
        if objects:
            status_name = {
                "running": "🟢 运行中 (Running)",
                "pending": "⏳ 等待中 (Pending)",
                "done": "✅ 已完成 (Done)",
                "error": "❌ 错误 (Error)",
            }[status_type]

            report_parts.append(f"\n🔸--- {status_name} ({len(objects)}) ---")
            report_parts.extend([format_chat_object_info(obj) for obj in objects])
        else:
            status_name = {
                "running": "🟢 运行中 (Running)",
                "pending": "⏳ 等待中 (Pending)",
                "done": "✅ 已完成 (Done)",
                "error": "❌ 错误 (Error)",
            }[status_type]
            report_parts.append(f"\n🔸--- {status_name} (0) ---")
            report_parts.append(" 无")

    full_report = "\n".join(report_parts)
    await matcher.send(full_report)


async def terminate_chat_object(stream_id: str, event: MessageEvent) -> bool:
    """终止指定的ChatObject"""
    all_objects: list[ChatObject] = chat_manager.get_objs(event)

    for obj in all_objects:
        if obj.stream_id.startswith(stream_id):  # 支持ID前缀匹配
            obj_instance: ChatObject = obj

            if obj_instance and (
                obj_instance.is_running() or obj_instance.is_waitting()
            ):
                with contextlib.suppress(Exception):
                    obj_instance.terminate()
                return True
            break

    return False


async def chatobj_manage(
    event: MessageEvent, matcher: Matcher, bot: Bot, args: Message = CommandArg()
):
    """处理chatobj命令"""
    plain_args = args.extract_plain_text().strip().lower()

    if plain_args in ["", "status", "show"]:
        # 显示所有ChatObject的状态
        status_dict = get_chat_objects_status(event)
        await send_status_report(matcher, status_dict)

    elif plain_args.startswith("terminate ") or plain_args.startswith("kill "):
        # 终止指定的ChatObject
        stream_id_prefix = plain_args.split(" ", 1)[1] if " " in plain_args else ""
        if len(stream_id_prefix) < 4:  # 至少需要4位前缀
            await matcher.finish("⚠️ 请输入至少4位的ID前缀来终止会话")

        success = await terminate_chat_object(stream_id_prefix, event)
        if success:
            await matcher.finish(f"✅ 已尝试终止ID为 '{stream_id_prefix}' 的会话")
        else:
            await matcher.finish(
                f"❌ 未找到匹配ID前缀为 '{stream_id_prefix}' 的运行中会话"
            )

    elif plain_args == "clear" or plain_args == "clean":
        count = 0
        objs = chat_manager.get_objs(event)
        for obj in objs:
            if obj.is_done():
                count += 1
                with contextlib.suppress(Exception):
                    obj.terminate()
            objs.remove(obj)
        await matcher.finish(f"🧹 已清除 {count} 个已完成的会话")

    elif plain_args == "help":
        help_text = (
            "ℹ️ ChatObject管理命令:\n"
            "🔸 /chatobj - 显示所有会话状态\n"
            "🔸 /chatobj status - 显示所有会话状态\n"
            "🔸 /chatobj terminate <ID前缀> - 终止指定会话\n"
            "🔸 /chatobj kill <ID前缀> - 终止指定会话\n"
            "🔸 /chatobj clear - 清除已完成的会话\n"
            "🔸 /chatobj help - 显示此帮助"
        )
        await matcher.finish(help_text)

    else:
        await matcher.finish("⚠️ 无效的命令参数，使用 '/chatobj help' 查看帮助")
