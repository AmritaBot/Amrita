"""Amrita CLI主命令模块

该模块实现了Amrita CLI的主要命令，包括项目创建、初始化、运行、依赖检查等功能。
"""

import importlib.metadata as metadata
import os
import subprocess
import sys
import typing
from copy import deepcopy
from pathlib import Path
from typing import Any

import click
import nonebot
import toml
import tomli_w
from pydantic import BaseModel, Field

import amrita

from ..cli import (
    IS_IN_VENV,
    check_nb_cli_available,
    check_optional_dependency,
    cli,
    error,
    info,
    install_optional_dependency,
    install_optional_dependency_no_venv,
    question,
    run_proc,
    should_update,
    stdout_run_proc,
    success,
    warn,
)
from ..resource import DOTENV, DOTENV_DEV, DOTENV_PROD, GITIGNORE, README
from ..utils.logging import LoggingData
from ..utils.utils import get_amrita_version


class Pyproject(BaseModel):
    """Pyproject.toml项目配置模型"""

    name: str
    description: str = ""
    version: str = "0.1.0"
    dependencies: list[str] = Field(
        default_factory=lambda: [f"amrita[full]>={get_amrita_version()}"]
    )
    readme: str = "README.md"
    requires_python: str = Field(default=">=3.10, <3.14", alias="requires-python")


class NonebotTool(BaseModel):
    """Nonebot工具配置模型"""

    plugins: list[str] = [
        "nonebot_plugin_orm",
    ]
    adapters: list[dict[str, Any]] = [
        {"name": "OneBot V11", "module_name": "nonebot.adapters.onebot.v11"},
    ]
    plugin_dirs: list[str] = []


class RUFFLint(BaseModel):
    """Ruff lint工具配置模型"""

    select: list[str] = [
        "F",  # Pyflakes
        "W",  # pycodestyle warnings
        "E",  # pycodestyle errors
        "UP",  # pyupgrade
        "ASYNC",  # flake8-async
        "C4",  # flake8-comprehensions
        "T10",  # flake8-debugger
        "PYI",  # flake8-pyi
        "PT",  # flake8-pytest-style
        "Q",  # flake8-quotes
        "RUF",  # Ruff-specific rules
        "I",  # isort
        "PERF",  # pylint-performance
    ]
    ignore: list[str] = [
        "E402",  # module-import-not-at-top-of-file
        "E501",  # line-too-long
        "UP037",  # quoted-annotation
        "RUF001",  # ambiguous-unicode-character-string
        "RUF002",  # ambiguous-unicode-character-docstring
        "RUF003",  # ambiguous-unicode-character-comment
    ]


class RUFFTool(BaseModel):
    """Ruff工具配置模型"""

    line_length: int = Field(default=88, alias="line-length")
    target_version: str = Field(default="py310", alias="target-version")
    lint: RUFFLint = RUFFLint()


class SetupToolPackagesFinder(BaseModel):
    """Setup工具配置模型"""

    exclude: list[str] = Field(
        default_factory=lambda: [
            "__pycache__",
            "*.pyc",
        ]
    )
    include: list[str] = Field(default_factory=lambda: ["plugins", "src/plugins"])


class SetupToolPackages(BaseModel):
    """Setup工具配置模型"""

    find: SetupToolPackagesFinder = SetupToolPackagesFinder()


class SetupTool(BaseModel):
    """Setup工具配置模型"""

    packages: SetupToolPackages = SetupToolPackages()


class UVTool(BaseModel):
    """uv工具配置模型"""

    dev_denpencies: list[str] = Field(
        default_factory=lambda: [
            "ruff>=0.12.8",
            "nonebot-plugin-orm[default]>=0.8.2",
            "pyright>=1.1.407",
        ],
        alias="dev-dependencies",
    )
    package: bool = True


class AmritaTool(BaseModel):
    """Amrita工具配置模型"""

    plugins: list[str] = [
        "amrita.plugins.chat",
        "amrita.plugins.manager",
        "amrita.plugins.menu",
        "amrita.plugins.perm",
    ]


class Tool(BaseModel):
    """工具配置模型"""

    nonebot: NonebotTool = NonebotTool()
    amrita: AmritaTool = AmritaTool()
    ruff: RUFFTool = RUFFTool()
    uv: UVTool = UVTool()
    pyright: dict[str, Any] = Field(
        default_factory=lambda: {"typeCheckingMode": "standard"}
    )
    setuptools: SetupTool = SetupTool()


class PyprojectFile(BaseModel):
    """Pyproject文件模型"""

    project: Pyproject = Pyproject(name="amrita")
    tool: Tool = Tool()


T = typing.TypeVar("T", bound=dict)


def update_dict(data: T, update_data: dict[str, Any]) -> T:
    """
    递归更新字典

    Args:
        data: 要更新的目标字典
        update_data: 包含更新值的源字典
    """
    data, update_data = deepcopy(data), deepcopy(update_data)
    for key, value in update_data.items():
        if key not in data:
            data[key] = value
        elif key in data and isinstance(data[key], dict) and isinstance(value, dict):
            data[key] = update_dict(data[key], value)
    return data


def init_project(
    project_dir: Path, project_name: str, description: str, python_version: str
):
    project_dir.resolve()  # 解析project_dir，防止可能的CLI注入
    # 创建项目目录结构
    os.makedirs(str(project_dir / "plugins"), exist_ok=True)
    os.makedirs(str(project_dir / "data"), exist_ok=True)
    os.makedirs(str(project_dir / "config"), exist_ok=True)
    # 创建pyproject.toml
    data = PyprojectFile(
        project=Pyproject(name=project_name, description=description)
    ).model_dump(by_alias=True)

    with open(project_dir / "pyproject.toml", "w", encoding="utf-8") as f:
        f.write(toml.dumps(data))

    # 创建其他项目文件
    if not (project_dir / ".env").exists():
        with open(project_dir / ".env", "w", encoding="utf-8") as f:
            f.write(DOTENV)
    if not (project_dir / ".env.prod").exists():
        with open(project_dir / ".env.prod", "w", encoding="utf-8") as f:
            f.write(DOTENV_PROD)
    if not (project_dir / ".env.dev").exists():
        with open(project_dir / ".env.dev", "w", encoding="utf-8") as f:
            f.write(DOTENV_DEV)
    with open(project_dir / ".gitignore", "w", encoding="utf-8") as f:
        f.write(GITIGNORE)
    with open(project_dir / "README.md", "w", encoding="utf-8") as f:
        f.write(README.format(project_name=project_name))
    with open(project_dir / ".python-version", "w", encoding="utf-8") as f:
        f.write(python_version)
    try:
        if not os.path.exists(str(project_dir / ".git")) or not os.path.isdir(
            str(project_dir / ".git")
        ):
            run_proc(["git", "init", str(project_dir)])
    except Exception as e:
        click.echo(error(f"无法初始化Git仓库：{e}"))


@cli.command()
def version():
    """打印版本号。

    显示Amrita和NoneBot的版本信息。
    """
    try:
        version = get_amrita_version()
        click.echo(f"Amrita 版本: {version}")

        # 尝试获取NoneBot版本
        try:
            nb_version = metadata.version("nonebot2")
            click.echo(f"NoneBot 版本: {nb_version}")
        except metadata.PackageNotFoundError:
            click.echo(warn("NoneBot 未安装"))

    except metadata.PackageNotFoundError:
        click.echo(error("Amrita 未正确安装"))


@cli.command()
def check_dependencies():
    """检查依赖。

    检查项目依赖是否完整，如不完整则提供修复选项。

    """
    click.echo(info("正在检查Amrita完整依赖..."))

    # 检查uv是否可用
    try:
        stdout_run_proc(["uv", "--version"])
    except (subprocess.CalledProcessError, FileNotFoundError):
        click.echo(error("UV 未安装，请安装UV后再试！"))

    # 检查amrita[full]依赖
    if check_optional_dependency():
        click.echo(success("完成依赖检查"))
    else:
        click.echo(error("已检查到依赖存在异常。"))
        fix: bool = click.confirm(question("您想要修复它吗？"))
        if fix:
            return install_optional_dependency()


@cli.command()
@click.option("--project-name", "-p", help="项目名称")
@click.option("--description", "-d", help="项目描述")
@click.option("--python-version", "-py", help="Python版本要求", default=">=3.10, <4.0")
@click.option("--this-dir", "-t", is_flag=True, help="使用当前目录")
def create(project_name, description, python_version, this_dir):
    """创建一个新项目。

    创建一个新的Amrita项目，包括目录结构和必要文件。

    Args:
        project_name: 项目名称
        description: 项目描述
        python_version: Python版本要求
        this_dir: 是否在当前目录创建项目
    """
    cwd = Path(os.getcwd())
    project_name = project_name or click.prompt(question("项目名称"), type=str)
    description = description or click.prompt(
        question("项目描述"), type=str, default=""
    )

    project_dir = cwd / project_name if not this_dir else cwd

    if project_dir.exists() and project_dir.is_dir() and list(project_dir.iterdir()):
        click.echo(warn(f"项目 `{project_name}` 看起来已经存在了."))
        overwrite = click.confirm(question("你想要覆盖它们吗?"), default=False)
        if not overwrite:
            return

    click.echo(info(f"正在创建项目 {project_name}..."))

    init_project(project_dir, project_name, description, python_version)
    # 安装依赖
    if click.confirm(question("您现在想要安装依赖吗?"), default=True):
        click.echo(info("正在安装依赖......"))
        if click.confirm(
            question("您想要使用虚拟环境吗（这通常是推荐的做法）?"), default=True
        ):
            os.chdir(str(project_dir))
            if not install_optional_dependency():
                click.echo(error("出现了一些问题，我们无法安装依赖。"))
                return
        elif not install_optional_dependency_no_venv():
            click.echo(error("无法安装依赖项。"))
            return
    click.echo(success(f"您的项目 {project_name} 已完成创建!"))
    click.echo(info("您接下来可以运行以下命令启动项目:"))
    click.echo(info(f"  cd {project_name if not this_dir else '.'}"))
    click.echo(info("  amrita run"))


@cli.command()
def entry():
    """在当前目录生成bot.py入口文件。"""
    click.echo(info("正在生成 bot.py..."))
    if os.path.exists("bot.py"):
        click.echo(error("bot.py 已存在。"))
        return
    with open("bot.py", "w") as f:
        f.write(
            open(str(Path(__file__).parent.parent / "bot.py"), encoding="utf-8").read()
        )


@cli.command()
@click.option("--run", "-r", is_flag=True, help="运行项目而不安装依赖。")
def run(run: bool):
    """运行Amrita项目。

    Args:
        run: 是否直接运行项目而不安装依赖
    """
    if run:
        try:
            # 添加当前目录到sys.path以确保插件能被正确导入
            if "." not in sys.path:
                sys.path.insert(0, ".")
            from amrita import bot

            bot.main()
        except ImportError as e:
            click.echo(error(f"错误，依赖缺失: {e}"))
            return
        except Exception as e:
            click.echo(error(f"在运行Bot时发生了一些问题: {e}"))
            return
        return

    if not os.path.exists("pyproject.toml"):
        click.echo(error("未找到 pyproject.toml"))
        return

    # 依赖检测和安装
    if not check_optional_dependency():
        click.echo(warn("缺少可选依赖 'full'"))
        if not install_optional_dependency():
            click.echo(error("安装可选依赖 'full' 失败"))
            return

    click.echo(info("正在启动项目"))
    # 构建运行命令
    cmd = ["uv", "run", "amrita", "run", "--run"]
    try:
        run_proc(cmd)
    except Exception:
        click.echo(error("运行项目时出现问题。"))
        return


@cli.command()
@click.option("--description", "-d", help="项目描述", default="")
def init(description):
    """将当前目录初始化为Amrita项目。

    Args:
        description: 项目描述
    """
    overwrite = False
    description = description or ""
    cwd = Path(os.getcwd()).resolve()
    project_name = cwd.name

    if (cwd / "pyproject.toml").exists():
        click.echo(warn("项目已初始化。"))
        overwrite = click.confirm(question("您想要覆盖现有文件吗?"), default=False)
        if not overwrite:
            return

    click.echo(info(f"正在初始化项目 {project_name}..."))

    init_project(cwd, project_name, description, "3.10")
    # 安装依赖
    click.echo(info("正在安装依赖..."))
    if not install_optional_dependency():
        click.echo(error("安装依赖失败。"))
        return

    click.echo(success("项目初始化成功！"))
    click.echo(info("下一步: amrita run"))


@cli.command()
def fix_pyproject():
    """修复pyproject.toml。"""
    if not os.path.exists("pyproject.toml"):
        click.echo(error("未找到 pyproject.toml"))
        return
    click.echo(info("正在修复 pyproject.toml..."))
    with open("pyproject.toml", encoding="utf-8") as f:
        data = toml.load(f)
    default_config = PyprojectFile()
    data = update_dict(data, default_config.model_dump(by_alias=True))
    click.echo(info("正在写入 pyproject.toml..."))
    with open("pyproject.toml", "w", encoding="utf-8") as f:
        f.write(tomli_w.dumps(data))
        click.echo(success("pyproject.toml 已写入。"))


@cli.command()
def proj_info():
    """显示项目信息。

    显示项目信息，包括名称、版本、描述和依赖等。
    """
    if not os.path.exists("pyproject.toml"):
        click.echo(error("未找到 pyproject.toml。"))
        return

    try:
        with open("pyproject.toml", encoding="utf-8") as f:
            data = toml.load(f)

        project_info = data.get("project", {})
        click.echo(success("项目信息:"))
        click.echo(f"  名称: {project_info.get('name', 'N/A')}")
        click.echo(f"  版本: {project_info.get('version', 'N/A')}")
        click.echo(f"  描述: {project_info.get('description', 'N/A')}")
        click.echo(f"  Python: {project_info.get('requires-python', 'N/A')}")

        dependencies = project_info.get("dependencies", [])
        if dependencies:
            click.echo("  依赖:")
            for dep in dependencies:
                click.echo(f"    - {dep}")

        from .plugin import echo_plugins

        echo_plugins()

    except Exception as e:
        click.echo(error(f"读取项目信息时出错: {e}"))


@cli.command(
    context_settings={
        "ignore_unknown_options": True,
    }
)
@click.argument("orm_args", nargs=-1, type=click.UNPROCESSED)
def orm(orm_args):
    """直接运行nb-orm命令。

    Args:
        orm_args: 传递给orm的参数
    """
    amrita.init()
    amrita.load_plugins()
    nonebot.require("nonebot_plugin_orm")
    from nonebot_plugin_orm import __main__

    __main__.main(orm_args)


@cli.command()
@click.option("--count", "-c", default="10", help="获取数量")
@click.option("--details", "-d", is_flag=True, help="显示详细信息")
def event(count: str, details: bool):
    """获取最近的事件(默认10个)。"""
    if not count.isdigit():
        click.echo(error("数量必须为大于0的正整数."))
        return
    if IS_IN_VENV:
        from amrita import init

        init()
        click.echo(
            success(
                f"获取数量为 {count} 的事件...",
            )
        )
        events = LoggingData._get_data_sync()
        if not events.data:
            click.echo(warn("没有日志事件被找到。"))
            return
        for event in events.data[-int(count) :]:
            click.echo(
                f"- {event.time.strftime('%Y-%m-%d %H:%M:%S')} {event.log_level} {event.description}"
                + (f"\n   |__{event.message}" if details else "")
            )
        click.echo(info(f"总共 {len(events.data)} 个事件。"))
    else:
        extend_list = []
        if details:
            extend_list.append("--details")
        run_proc(["uv", "run", "amrita", "event", "--count", count, *extend_list])


@cli.command(
    context_settings={
        "ignore_unknown_options": True,
    }
)
@click.argument("nb_args", nargs=-1, type=click.UNPROCESSED)
def nb(nb_args):
    """直接运行nb-cli命令。

    Args:
        nb_args: 传递给nb-cli的参数
    """
    if not check_nb_cli_available():
        click.echo(error("nb-cli 不可用。请使用 'uv add nb-cli' 安装"))
        return

    try:
        # 将参数传递给nb-cli
        click.echo(info("正在运行 nb-cli..."))
        run_proc(["nb", *list(nb_args)])
    except subprocess.CalledProcessError as e:
        if e.returncode == 127:
            click.echo(error("nb-cli 不可用。请使用 'uv add nb-cli' 安装"))
        elif e.returncode == 2:
            click.echo(error(bytes(e.stdout).decode("utf-8")))
            click.echo(error("nb-cli 命令失败，您的命令是否正确？"))
        else:
            click.echo(error(f"nb-cli 命令失败，退出代码 {e.returncode}"))


@cli.command()
@click.option("--ignore-venv", "-i", is_flag=True, help="忽略Venv环境")
def test(ignore_venv: bool):
    """运行Amrita项目的负载测试。"""
    if not check_optional_dependency():
        return click.echo(error("缺少可选依赖 'full'"))
    if ignore_venv or IS_IN_VENV:
        click.echo(info("正在运行负载测试..."))
        from amrita import load_test

        try:
            load_test.main()
        except Exception as e:
            click.echo(error("糟糕！在预加载时出现问题(运行 on_startup 钩子)!"))
            click.echo(error(f"错误: {e}"))
            exit(1)
        else:
            click.echo(info("完成!"))
    else:
        run_proc(["uv", "run", "amrita", "test", "--ignore-venv"])


@cli.command()
def update():
    """更新Amrita"""
    click.echo(info("正在检查更新..."))
    need_update, version = should_update()
    if need_update:
        if not IS_IN_VENV:
            click.echo(warn(f"新版本的Amrita已就绪: {version}"))
        click.echo(info("正在更新..."))
        run_proc(
            ["pip", "install", f"amrita=={version}"]
            + (["--break-system-packages"] if sys.platform.lower() == "linux" else [])
        )
    if not IS_IN_VENV:
        click.echo(info("正在检查虚拟环境Amrita..."))
        if not os.path.exists(".venv"):
            click.echo(warn("未找到虚拟环境，已跳过。"))
            return
        venv_version = (
            stdout_run_proc(["uv", "run", "pip", "show", "amrita"])
            .split("\n")[1]
            .split(" ")[1]
            .strip()
        )
        click.echo(info(f"检测到虚拟环境Amrita: {venv_version}，目标：{version}"))
        if venv_version < version:
            click.echo(info("正在更新虚拟环境Amrita..."))
            try:
                run_proc(["uv", "add", f"amrita=={version}"])
            except Exception as e:
                click.echo(error("虚拟环境Amrita更新失败!"))
                click.echo(error(f"错误: {e}"))
                exit(1)
