import typing
from collections.abc import Awaitable, Callable
from typing import Any, ClassVar

from typing_extensions import Self

from .models import FunctionDefinitionSchema, ToolContext, ToolData, ToolFunctionSchema

T = typing.TypeVar("T")

class ToolsManager:
    _instance = None
    _models: ClassVar[dict[str, ToolData]] = {}
    _disabled_tools: ClassVar[set[str]] = (
        set()
    )  # 禁用的工具，使用has_tool与get_tool不会返回禁用工具

    def __new__(cls) -> Self:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def has_tool(self, name: str) -> bool:
        if name in self._disabled_tools:
            return False
        return name in self._models

    def get_tool(self, name: str, default: T = None) -> ToolData | T | None:
        if not self.has_tool(name):
            return default
        return self._models.get(name, default)

    def get_tool_meta(
        self, name: str, default: T | None = None
    ) -> ToolFunctionSchema | None | T:
        func_data = self.get_tool(name)
        if func_data is None:
            return default
        if isinstance(func_data, ToolData):
            return func_data.data
        return default

    def get_tool_func(
        self, name: str, default: Any | None = None
    ) -> Callable[[dict[str, Any]], Awaitable[str]] | None | Any:
        func_data = self.get_tool(name)
        if func_data is None:
            return default
        if isinstance(func_data, ToolData):
            return func_data.func
        return default

    def get_tools(self) -> dict[str, ToolData]:
        return {
            name: data
            for name, data in self._models.items()
            if name not in self._disabled_tools
        }

    def tools_meta(self) -> dict[str, ToolFunctionSchema]:
        return {k: v.data for k, v in self._models.items()}

    def tools_meta_dict(self, **kwargs) -> dict[str, dict[str, Any]]:
        return {k: v.data.model_dump(**kwargs) for k, v in self._models.items()}

    def register_tool(self, tool: ToolData) -> None:
        if tool.data.function.name not in self._models:
            self._models[tool.data.function.name] = tool
        else:
            raise ValueError(f"工具 {tool.data.function.name} 已经存在")

    def remove_tool(self, name: str) -> None:
        if name in self._models:
            del self._models[name]


def on_tools(
    data: FunctionDefinitionSchema,
    custom_run: bool = False,
    strict: bool = False,
):
    """Tools注册装饰器

    Args:
        data (FunctionDefinitionSchema): 函数元数据
        custom_run (bool, optional): 是否启用自定义运行模式. Defaults to False.
        strict (bool, optional): 是否启用严格模式. Defaults to False.
    """

    def decorator(
        func: Callable[[dict[str, Any]], Awaitable[str]]
        | Callable[[ToolContext], Awaitable[str | None]],
    ):
        tool_data = ToolData(
            func=func,
            data=ToolFunctionSchema(function=data, type="function", strict=strict),
            custom_run=custom_run,
        )
        ToolsManager().register_tool(tool_data)
        return func

    return decorator
