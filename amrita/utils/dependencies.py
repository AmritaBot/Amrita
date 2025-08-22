"""依赖检查工具模块

提供检查可选依赖是否安装的功能。
"""

import importlib
import importlib.metadata
import re
import typing


def check_dependency_package(package_name: str) -> bool:
    """
    检查指定的包是否已安装（使用 importlib.metadata）

    Args:
        package_name (str): 包名称

    Returns:
        bool: 如果包已安装返回True，否则返回False
    """
    try:
        importlib.metadata.version(package_name)
        return True
    except importlib.metadata.PackageNotFoundError:
        return False


def self_get_optional_dependency() -> list[str]:
    # 获取项目元数据
    metadata = importlib.metadata.metadata("amrita")
    requires_dist = metadata.json["requires_dist"]

    # 提取带有 extra == "full" 标记的依赖
    optional_deps = []
    for req in requires_dist:
        if 'extra == "full"' in req or "extra == 'full'" in req:
            # 提取包名（移除版本约束和其他标记）
            package_name = req.split(";")[0].strip()
            optional_deps.append(package_name)

    return optional_deps


def self_check_optional_dependency():
    def match_package_name(package_name) -> str:
        return typing.cast(
            re.Match[str], re.match(r"^\s*([\w\-\.]+)", package_name)
        ).groups()[0]

    deps = self_get_optional_dependency()
    missed_deps = [
        dep for dep in deps if not check_dependency_package(match_package_name(dep))
    ]
    return not missed_deps, missed_deps
