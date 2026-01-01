"""
UniConfigManager使用示例
这个模块演示如何使用UniConfigManager进行配置管理
"""

from nonebot import get_driver, on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER
from nonebot.plugin import on_message
from pydantic import BaseModel, Field

from amrita.config_manager import BaseDataManager, UniConfigManager


# 定义一个示例配置类
class ExampleConfig(BaseModel):
    """示例配置类"""

    enable: bool = Field(default=True, description="是否启用功能")
    max_connections: int = Field(default=10, description="最大连接数")
    timeout: float = Field(default=30.0, description="超时时间（秒）")
    allowed_users: list[str] = Field(default=[], description="允许的用户列表")
    api_keys: dict[str, str] = Field(default={}, description="API密钥映射")


# 创建配置管理器
class ExampleDataManager(BaseDataManager[ExampleConfig]):
    """示例数据管理器"""

    config: ExampleConfig
    config_class: type[ExampleConfig]
    # __lateinit__ = True  # 标记为延迟初始化(实际是调用时才初始化)


# 配置管理命令
config_command = on_command(
    "config_example", permission=SUPERUSER, priority=10, block=True
)


@config_command.handle()
async def handle_config_command(event: MessageEvent, args: Message = CommandArg()):
    """处理配置相关命令"""

    # 获取参数
    plain_text = args.extract_plain_text().strip()

    if plain_text == "show":
        # 安全获取配置
        config = await ExampleDataManager().safe_get_config()
        await config_command.send(f"当前配置:\n{config}")
    elif plain_text == "update":
        # 安全获取配置
        config = await ExampleDataManager().safe_get_config()
        config.enable = not config.enable
        config.max_connections += 1

        # 保存配置
        await UniConfigManager().save_config()
        await config_command.send(f"配置已更新:\n{config}")
    else:
        await config_command.send(
            "使用方法:\n- config_example show (显示配置)\n- config_example update (更新配置)"
        )


# 示例：在驱动启动时加载配置
driver = get_driver()


@driver.on_startup
async def startup():
    """启动时加载配置"""
    print("正在启动并加载配置...")

    # 安全获取配置
    config = await ExampleDataManager().safe_get_config()
    print(f"配置已加载: {config}")


# 演示如何在消息处理器中使用配置
demo_message = on_message(priority=15, block=False)


@demo_message.handle()
async def handle_demo_message(event: MessageEvent):
    """演示在消息处理器中使用配置"""

    # 安全获取配置
    config = await ExampleDataManager().safe_get_config()

    if not config.enable:
        # 如果功能未启用，直接返回
        return

    # 检查是否在允许的用户列表中
    user_id = event.get_user_id()
    if config.allowed_users and user_id not in config.allowed_users:
        await demo_message.send("您没有权限使用此功能")
        return

    # 处理消息
    await demo_message.send(f"功能已启用，收到您的消息: {event.get_plaintext()}")


# 演示如何在命令中使用配置
demo_command = on_command("demo", priority=10, block=True)


@demo_command.handle()
async def handle_demo_command(event: MessageEvent):
    """演示在命令中使用配置"""

    # 安全获取配置
    config = await ExampleDataManager().safe_get_config()

    if not config.enable:
        await demo_command.finish("此功能当前未启用")

    # 检查API密钥
    user_id = event.get_user_id()
    if user_id in config.api_keys:
        await demo_command.send(f"用户 {user_id} 有API密钥")
    else:
        await demo_command.send(f"用户 {user_id} 没有API密钥")
