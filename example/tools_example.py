"""
示例工具模块
这个模块演示如何使用 on_tools 装饰器来注册工具
"""

import asyncio
import random
from typing import Any

from amrita.plugins.chat.utils.llm_tools.manager import on_tools
from amrita.plugins.chat.utils.llm_tools.models import (
    FunctionDefinitionSchema,
    FunctionParametersSchema,
    FunctionPropertySchema,
)


# 定义一个天气查询工具
@on_tools(
    data=FunctionDefinitionSchema(
        name="get_weather",
        description="获取指定城市的天气信息",
        parameters=FunctionParametersSchema(
            type="object",
            properties={
                "city": FunctionPropertySchema(type="string", description="城市名称")
            },
            required=["city"],
        ),
    )
)
async def get_weather(args: dict[str, str]) -> str:
    """
    模拟查询天气信息
    """
    city = args.get("city", "未知城市")
    # 模拟API调用延迟
    await asyncio.sleep(1)

    # 随机生成天气数据
    weather_conditions = ["晴朗", "多云", "阴天", "小雨", "大雨", "雪天"]
    current_weather = random.choice(weather_conditions)
    temperature = random.randint(-10, 40)

    result = f"城市 {city} 的天气为 {current_weather}，温度 {temperature}°C"
    print(f"查询天气: {result}")
    return result


# 定义一个计算器工具
@on_tools(
    data=FunctionDefinitionSchema(
        name="calculate",
        description="执行基本数学计算",
        parameters=FunctionParametersSchema(
            type="object",
            properties={
                "expression": FunctionPropertySchema(
                    type="string", description="数学表达式，如 '2 + 3 * 4'"
                )
            },
            required=["expression"],
        ),
    )
)
async def calculate(args: dict[str, str]) -> str:
    """
    执行基本计算
    注意：在生产环境中，应该使用更安全的表达式解析器而不是 eval
    """
    expression = args.get("expression", "")

    # 简单的安全检查，只允许数字和基本运算符
    allowed_chars = set("0123456789+-*/().% ")
    if not all(c in allowed_chars for c in expression):
        return "错误：表达式包含不允许的字符"

    try:
        # 计算结果
        result = eval(expression)
        formatted_result = f"表达式 '{expression}' 的结果是 {result}"
        print(f"计算: {formatted_result}")
        return formatted_result
    except Exception as e:
        error_msg = f"计算错误：{e!s}"
        print(f"计算出错: {error_msg}")
        return error_msg


# 定义一个搜索工具
@on_tools(
    data=FunctionDefinitionSchema(
        name="web_search",
        description="模拟网络搜索功能",
        parameters=FunctionParametersSchema(
            type="object",
            properties={
                "query": FunctionPropertySchema(
                    type="string", description="搜索查询词"
                ),
                "result_count": FunctionPropertySchema(
                    type="integer", description="返回结果数量", minItems=1, maxItems=10
                ),
            },
            required=["query"],
        ),
    )
)
async def web_search(args: dict[str, Any]) -> str:
    """
    模拟网络搜索
    """
    query = args.get("query", "")
    result_count = args.get("result_count", 3)

    # 确保结果数量在合理范围内
    if result_count < 1:
        result_count = 1
    elif result_count > 10:
        result_count = 10

    # 模拟搜索结果
    mock_results = [
        f"关于 '{query}' 的搜索结果 1",
        f"关于 '{query}' 的搜索结果 2",
        f"关于 '{query}' 的搜索结果 3",
        f"关于 '{query}' 的搜索结果 4",
        f"关于 '{query}' 的搜索结果 5",
    ]

    results = mock_results[:result_count]
    formatted_results = "\n".join(results)

    final_result = f"搜索 '{query}' 的结果：\n{formatted_results}"
    print(f"搜索: {final_result}")
    return final_result


# 定义一个时间工具
@on_tools(
    data=FunctionDefinitionSchema(
        name="get_current_time",
        description="获取当前时间",
        parameters=FunctionParametersSchema(
            type="object",
            properties={},
        ),
    )
)
async def get_current_time(args: dict[str, str]) -> str:
    """
    获取当前时间
    """
    from datetime import datetime

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result = f"当前时间是 {current_time}"
    print(f"获取时间: {result}")
    return result
