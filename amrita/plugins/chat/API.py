"""聊天插件API模块

该模块提供了聊天插件的公共API接口，包括菜单管理、管理员操作、聊天功能等核心功能的封装。
"""

from __future__ import annotations

from nonebot import logger

from amrita.utils.admin import send_to_admin

from .config import Config, ConfigManager, config_manager
from .on_event import on_before_chat, on_before_poke, on_chat, on_event, on_poke
from .utils.libchat import (
    AdapterManager,
    ModelAdapter,
    get_chat,
    tools_caller,
)
from .utils.llm_tools.manager import ToolsManager, on_tools
from .utils.llm_tools.mcp_client import MCP_SERVER_SCRIPT_TYPE, ClientManager, MCPClient
from .utils.llm_tools.models import (
    FunctionDefinitionSchema,
    FunctionParametersSchema,
    FunctionPropertySchema,
    ToolChoice,
    ToolContext,
    ToolData,
    ToolFunctionSchema,
)
from .utils.memory import get_memory_data
from .utils.models import InsightsModel
from .utils.tokenizer import Tokenizer, hybrid_token_count


class Admin:
    """管理员管理类

    负责处理与管理员相关的操作，如发送消息、错误处理和管理员权限管理。
    """

    config: Config

    def __init__(self):
        """构造函数，初始化配置"""
        self.config = config_manager.ins_config

    async def send_with(self, msg: str) -> Admin:
        """异步发送消息给管理员。

        参数:
        - msg (str): 要发送的消息内容。

        返回:
        - Admin: 返回Admin实例，支持链式调用。
        """
        await send_to_admin(msg)
        return self

    async def send_error(self, msg: str) -> Admin:
        """异步发送错误消息给管理员，并记录错误日志。

        参数:
        - msg (str): 要发送的错误消息内容。

        返回:
        - Admin: 返回Admin实例，支持链式调用。
        """
        logger.error(msg)
        await send_to_admin(msg)
        return self

    def is_admin(self, user_id: str) -> bool:
        """检查用户是否是管理员。

        参数:
        - user_id (str): 用户ID。

        返回:
        - bool: 用户是否是管理员。
        """
        return int(user_id) in self.config.admin.admins


class Chat:
    """聊天处理类

    Chat 类用于处理与LLM相关操作，如获取消息响应、调用工具等。
    """

    config: Config

    def __init__(self):
        """构造函数，初始化配置"""
        self.config = config_manager.ins_config

    async def get_msg(self, prompt: str, message: list):
        """获取LLM响应

        在消息列表前插入系统提示词，然后调用模型获取响应。

        :param prompt[str]: 系统提示词
        :param message[list]: 消息列表

        :returns: 模型响应结果
        """
        message.insert(0, {"role": "assistant", "content": prompt})
        return await self.get_msg_on_list(message)

    async def get_msg_on_list(self, message: list):
        """获取LLM响应

        直接使用提供的消息列表调用模型获取响应。

        :param message[list]: 消息列表

        :returns: 模型响应结果
        """
        return await get_chat(messages=message)

    async def call_tools(
        self,
        messages: list,
        tools: list,
        tool_choice: ToolChoice | None = None,
    ):
        """调用工具

        使用指定的工具和消息调用工具函数。

        :param messages: 消息列表
        :param tools: 工具列表
        :param tool_choice: 工具选择参数（可选）

        :returns: 工具调用结果
        """
        return await tools_caller(
            messages=messages, tools=tools, tool_choice=tool_choice
        )


__all__ = [
    "MCP_SERVER_SCRIPT_TYPE",
    "AdapterManager",
    "Admin",
    "Chat",
    "ClientManager",
    "ConfigManager",
    "FunctionDefinitionSchema",
    "FunctionParametersSchema",
    "FunctionPropertySchema",
    "InsightsModel",
    "MCPClient",
    "ModelAdapter",
    "Tokenizer",
    "ToolContext",
    "ToolData",
    "ToolFunctionSchema",
    "ToolsManager",
    "config_manager",
    "get_memory_data",
    "hybrid_token_count",
    "on_before_chat",
    "on_before_poke",
    "on_chat",
    "on_event",
    "on_poke",
    "on_tools",
    "tools_caller",
]
