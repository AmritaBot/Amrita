"""Amrita CLI主命令模块

该模块实现了Amrita CLI的主要命令，包括项目创建、初始化、运行、依赖检查等功能。
"""

import importlib.metadata as metadata
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import click
import toml
from pydantic import BaseModel, Field

from ..cli import (
    check_nb_cli_available,
    check_optional_dependency,
    cli,
    error,
    info,
    install_optional_dependency,
    install_optional_dependency_no_venv,
    question,
    run_proc,
    stdout_run_proc,
    success,
    warn,
)
from ..resource import DOTENV, DOTENV_DEV, DOTENV_PROD, GITIGNORE, README
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
    requires_python: str = ">=3.10, <4.0"


class NonebotTool(BaseModel):
    """Nonebot工具配置模型"""

    plugins: list[str] = [
        "nonebot_plugin_orm",
        "amrita.plugins.chat",
        "amrita.plugins.manager",
        "amrita.plugins.menu",
        "amrita.plugins.perm",
    ]
    adapters: list[dict[str, Any]] = [
        {"name": "OneBot V11", "module_name": "nonebot.adapters.onebot.v11"},
    ]
    plugin_dirs: list[str] = []


class Tool(BaseModel):
    """工具配置模型"""

    nonebot: NonebotTool = NonebotTool()


class PyprojectFile(BaseModel):
    """Pyproject文件模型"""

    project: Pyproject
    tool: Tool = Tool()


@cli.command()
def version():
    """Print the version number.

    显示Amrita和NoneBot的版本信息。
    """
    try:
        version = get_amrita_version()
        click.echo(f"Amrita version: {version}")

        # 尝试获取NoneBot版本
        try:
            nb_version = metadata.version("nonebot2")
            click.echo(f"NoneBot version: {nb_version}")
        except metadata.PackageNotFoundError:
            click.echo(warn("NoneBot is not installed"))

    except metadata.PackageNotFoundError:
        click.echo(error("Amrita is not installed properly"))


@cli.command()
@click.option("--self", "-s", help="Check directly in this environment", is_flag=True)
def check_dependencies(self):
    """Check dependencies.

    检查项目依赖是否完整，如不完整则提供修复选项。

    Args:
        self: 是否在当前环境中直接检查
    """
    click.echo(info("Checking dependencies..."))

    # 检查uv是否可用
    try:
        stdout_run_proc(["uv", "--version"])
    except (subprocess.CalledProcessError, FileNotFoundError):
        click.echo(error("uv is not available. Please install uv first."))

    # 检查amrita[full]依赖
    if check_optional_dependency(self):
        click.echo(success("Dependencies checked successfully!"))
    else:
        click.echo(error("Dependencies has problems"))
        if self:
            sys.exit(1)
        fix: bool = click.confirm(question("Do you want to fix it?"))
        if fix:
            return install_optional_dependency()


@cli.command()
@click.option("--project-name", "-p", help="Project name")
@click.option("--description", "-d", help="Project description")
@click.option(
    "--python-version", "-py", help="Python version requirement", default=">=3.10, <4.0"
)
@click.option("--this-dir", "-t", is_flag=True, help="Use current directory")
def create(project_name, description, python_version, this_dir):
    """Create a new project.

    创建一个新的Amrita项目，包括目录结构和必要文件。

    Args:
        project_name: 项目名称
        description: 项目描述
        python_version: Python版本要求
        this_dir: 是否在当前目录创建项目
    """
    cwd = Path(os.getcwd())
    project_name = project_name or click.prompt(question("Project name"), type=str)
    description = description or click.prompt(
        question("Project description"), type=str, default=""
    )

    project_dir = cwd / project_name if not this_dir else cwd

    if project_dir.exists() and project_dir.is_dir() and list(project_dir.iterdir()):
        click.echo(warn(f"Project {project_name} already exists."))
        overwrite = click.confirm(
            question("Do you want to overwrite existing files?"), default=False
        )
        if not overwrite:
            return

    click.echo(info(f"Creating project {project_name}..."))

    # 创建项目目录结构
    os.makedirs(str(project_dir / "plugins"), exist_ok=True)
    os.makedirs(str(project_dir / "data"), exist_ok=True)
    os.makedirs(str(project_dir / "config"), exist_ok=True)

    # 创建pyproject.toml
    data = PyprojectFile(
        project=Pyproject(
            name=project_name, description=description, requires_python=python_version
        )
    ).model_dump()

    with open(project_dir / "pyproject.toml", "w") as f:
        f.write(toml.dumps(data))

    # 创建其他项目文件
    if not (project_dir / ".env").exists():
        with open(project_dir / ".env", "w") as f:
            f.write(DOTENV)
    if not (project_dir / ".env.prod").exists():
        with open(project_dir / ".env.prod", "w") as f:
            f.write(DOTENV_PROD)
    if not (project_dir / ".env.dev").exists():
        with open(project_dir / ".env.dev", "w") as f:
            f.write(DOTENV_DEV)
    with open(project_dir / ".gitignore", "w") as f:
        f.write(GITIGNORE)
    with open(project_dir / "README.md", "w") as f:
        f.write(README.format(project_name=project_name))
    with open(project_dir / ".python-version", "w") as f:
        f.write("3.10\n")
    # 安装依赖
    if click.confirm(
        question("Do you want to install dependencies now?"), default=True
    ):
        click.echo(info("Installing dependencies..."))
        if click.confirm(question("Do you want to use venv?"), default=True):
            os.chdir(str(project_dir))
            if not install_optional_dependency():
                click.echo(error("Failed to install dependencies."))
                return
        elif not install_optional_dependency_no_venv():
            click.echo(error("Failed to install dependencies."))
            return
    click.echo(success(f"Project {project_name} created successfully!"))
    click.echo(info("Next steps:"))
    click.echo(info(f"  cd {project_name if not this_dir else '.'}"))
    click.echo(info("  amrita run"))


@cli.command()
def entry():
    """Generate a bot.py on current directory.

    在当前目录生成bot.py入口文件。
    """
    click.echo(info("Generating bot.py..."))
    if os.path.exists("bot.py"):
        click.echo(error("bot.py already exists."))
        return
    with open("bot.py", "w") as f:
        f.write(open(str(Path(__file__).parent.parent / "bot.py")).read())


@cli.command()
@click.option(
    "--run", "-r", is_flag=True, help="Run the project without installing dependencies."
)
def run(run: bool):
    """Run the project.

    运行Amrita项目。

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
            click.echo(error(f"Missing dependency: {e}"))
            return
        except Exception as e:
            click.echo(error(f"Runtime error: {e}"))
            return
        return

    if not os.path.exists("pyproject.toml"):
        click.echo(error("pyproject.toml not found"))
        return

    # 依赖检测和安装
    if not check_optional_dependency():
        click.echo(warn("Missing optional dependency 'full'"))
        if not install_optional_dependency():
            click.echo(error("Failed to install optional dependency 'full'"))
            return

    click.echo(info("Starting project"))

    # 构建运行命令
    cmd = ["uv", "run", "amrita", "run", "--run"]

    run_proc(cmd)


@cli.command()
@click.option("--description", "-d", help="Project description")
def init(description):
    """Initialize current directory as an Amrita project.

    将当前目录初始化为Amrita项目。

    Args:
        description: 项目描述
    """
    cwd = Path(os.getcwd())
    project_name = cwd.name

    if (cwd / "pyproject.toml").exists():
        click.echo(warn("Project already initialized."))
        overwrite = click.confirm(
            question("Do you want to overwrite existing files?"), default=False
        )
        if not overwrite:
            return

    click.echo(info(f"Initializing project {project_name}..."))

    # 创建目录结构
    os.makedirs(str(cwd / "plugins"), exist_ok=True)
    os.makedirs(str(cwd / "data"), exist_ok=True)
    os.makedirs(str(cwd / "config"), exist_ok=True)

    # 创建pyproject.toml
    data = PyprojectFile(
        project=Pyproject(
            name=project_name,
            description=description or "",
        )
    ).model_dump()
    if not (cwd / ".env").exists():
        with open(cwd / ".env", "w") as f:
            f.write(DOTENV)
    if not (cwd / ".env.prod").exists():
        with open(cwd / ".env.prod", "w") as f:
            f.write(DOTENV_PROD)
    if not (cwd / ".env.dev").exists():
        with open(cwd / ".env.dev", "w") as f:
            f.write(DOTENV_DEV)
    with open(cwd / "pyproject.toml", "w") as f:
        f.write(toml.dumps(data))
    with open(cwd / ".gitignore", "w") as f:
        f.write(GITIGNORE)
    with open(cwd / "README.md", "w") as f:
        f.write(README.format(project_name=project_name))
    with open(cwd / ".python-version", "w") as f:
        f.write("3.10\n")

    # 安装依赖
    click.echo(info("Installing dependencies..."))
    if not install_optional_dependency():
        click.echo(error("Failed to install dependencies."))
        return

    click.echo(success("Project initialized successfully!"))
    click.echo(info("Next steps: amrita run"))


@cli.command()
def proj_info():
    """Show project information.

    显示项目信息，包括名称、版本、描述和依赖等。
    """
    if not os.path.exists("pyproject.toml"):
        click.echo(error("No pyproject.toml found."))
        return

    try:
        with open("pyproject.toml") as f:
            data = toml.load(f)

        project_info = data.get("project", {})
        click.echo(success("Project Information:"))
        click.echo(f"  Name: {project_info.get('name', 'N/A')}")
        click.echo(f"  Version: {project_info.get('version', 'N/A')}")
        click.echo(f"  Description: {project_info.get('description', 'N/A')}")
        click.echo(f"  Python: {project_info.get('requires-python', 'N/A')}")

        dependencies = project_info.get("dependencies", [])
        if dependencies:
            click.echo("  Dependencies:")
            for dep in dependencies:
                click.echo(f"    - {dep}")

        from .plugin import echo_plugins

        echo_plugins()

    except Exception as e:
        click.echo(error(f"Error reading project info: {e}"))


@cli.command(
    context_settings={
        "ignore_unknown_options": True,
    }
)
@click.argument("nb_args", nargs=-1, type=click.UNPROCESSED)
def nb(nb_args):
    """Run nb-cli commands directly.

    直接运行nb-cli命令。

    Args:
        nb_args: 传递给nb-cli的参数
    """
    if not check_nb_cli_available():
        click.echo(
            error(
                "nb-cli is not available. Please install it with 'pip install nb-cli'"
            )
        )
        return

    try:
        # 将参数传递给nb-cli
        click.echo(info("Running nb-cli..."))
        run_proc(["nb", *list(nb_args)])
    except subprocess.CalledProcessError as e:
        if e.returncode == 127:
            click.echo(
                error(
                    "nb-cli is not available. Please install it with 'pip install nb-cli'"
                )
            )
        elif e.returncode == 2:
            click.echo(error(bytes(e.stdout).decode("utf-8")))
            click.echo(error("nb-cli command failed,is your command correct?"))
        else:
            click.echo(error(f"nb-cli command failed with exit code {e.returncode}"))


@cli.command()
def test():
    """Run a load test for Amrita project

    运行Amrita项目的负载测试。
    """
    if not check_optional_dependency():
        click.echo(error("Missing optional dependency 'full'"))
    else:
        from amrita import load_test

        try:
            load_test.main()
        except Exception as e:
            click.echo(
                error(
                    "OOPS!There is something wrong while pre-loading(Running on_startup hooks)!"
                )
            )
            click.echo(error(f"Error: {e}"))
            exit(1)
        else:
            click.echo(info("Done!"))
