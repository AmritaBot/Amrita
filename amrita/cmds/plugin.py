"""Amrita CLI插件管理模块

该模块实现了Amrita CLI的插件管理命令，包括插件的安装、创建、删除和列表查看等功能。
"""

import os
import subprocess
from pathlib import Path
from subprocess import CalledProcessError
from typing import Any

import click
import requests
import toml

from amrita.cli import (
    error,
    info,
    plugin,
    question,
    run_proc,
    stdout_run_proc,
    success,
    warn,
)
from amrita.resource import EXAMPLE_PLUGIN, EXAMPLE_PLUGIN_CONFIG


def get_package_metadata(package_name: str) -> dict[str, Any] | None:
    """获取PyPI包的元数据信息

    Args:
        package_name: 包名称

    Returns:
        包的元数据字典，如果获取失败则返回None
    """
    try:
        response = requests.get(f"https://pypi.org/pypi/{package_name}/json")
        response.raise_for_status()
        return response.json()
    except Exception:
        return


def pypi_install(name: str):
    """从PyPI安装插件

    Args:
        name: 插件名称
    """
    name = name.replace("_", "-")
    click.echo(info("Try to install plugin from pypi directly..."))
    metadata = get_package_metadata(name)
    if not metadata:
        click.echo(error("Package not found"))
        return
    click.echo(info(f"Downloading {name}..."))
    try:
        run_proc(["uv", "add", name])
    except CalledProcessError:
        click.echo(error(f"Failed to install {name}"))
        return
    click.echo(info("Installing..."))
    with open(
        "pyproject.toml",
    ) as f:
        data = toml.load(f)
        if "nonebot" not in data["tool"]:
            data["tool"]["nonebot"] = {}
            data["tool"]["nonebot"]["plugins"] = []
        if name.replace("-", "_") not in data["tool"]["nonebot"]["plugins"]:
            data["tool"]["nonebot"]["plugins"].append(name.replace("-", "_"))
    with open("pyproject.toml", "w") as f:
        toml.dump(data, f)
    click.echo(
        success(f"Plugin {name} added to pyproject.toml and installed successfully.")
    )


@plugin.command()
@click.argument("name")
@click.option(
    "--pypi", "-p", help="Install from PyPI directly", is_flag=True, default=False
)
def install(name: str, pypi: bool):
    """Install a plugin.

    安装指定的插件。

    Args:
        name: 插件名称
        pypi: 是否直接从PyPI安装
    """
    cwd = Path(os.getcwd())
    if (cwd / "plugins" / name).exists():
        click.echo(warn(f"Plugin {name} already exists."))
        return
    if pypi or name.replace("_", "-").startswith("amrita-plugin-"):
        pypi_install(name)
    else:
        try:
            run_proc(
                ["nb", "plugin", "install", name],
            )
        except Exception:
            click.echo(error(f"Failed to install plugin {name}.Package not found."))
            if click.confirm(question("Do you want to try installing it from pypi?")):
                return pypi_install(name)


@plugin.command()
@click.argument("name", default="")
def new(name: str):
    """Create a new plugin.

    创建一个新的插件。

    Args:
        name: 插件名称
    """
    cwd = Path(os.getcwd())
    if not name:
        name = click.prompt(question("Plugin name"))
    plugins_dir = cwd / "plugins"

    if not plugins_dir.exists():
        click.echo(error("Not in an Amrita project directory."))
        return

    plugin_dir = plugins_dir / name
    if plugin_dir.exists():
        click.echo(warn(f"Plugin {name} already exists."))
        overwrite = click.confirm(
            question("Do you want to overwrite it?"), default=False
        )
        if not overwrite:
            return

    os.makedirs(plugin_dir, exist_ok=True)

    # 创建插件文件
    with open(plugin_dir / "__init__.py", "w") as f:
        f.write(
            f"from . import {name.replace('-', '_')}\n\n__all__ = ['{name.replace('-', '_')}']\n"
        )

    with open(plugin_dir / f"{name.replace('-', '_')}.py", "w") as f:
        f.write(EXAMPLE_PLUGIN.format(name=name.replace("-", "_")))

    # 创建配置文件
    with open(plugin_dir / "config.py", "w") as f:
        f.write(EXAMPLE_PLUGIN_CONFIG.format(name=name.replace("-", "_")))

    click.echo(success(f"Plugin {name} created successfully!"))


@plugin.command()
@click.argument("name", default="")
def remove(name: str):
    """Remove a plugin.

    删除指定的插件。

    Args:
        name: 插件名称
    """
    if not name:
        name = click.prompt(question("Enter plugin name"))
    cwd = Path(os.getcwd())
    plugin_dir = cwd / "plugins" / name

    if not plugin_dir.exists():
        try:
            run_proc(
                ["nb", "plugin", "remove", name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except Exception:
            pass
        click.echo(error(f"Plugin {name} does not exist."))
        return

    confirm = click.confirm(
        question(f"Are you sure you want to remove plugin '{name}'?"), default=False
    )
    if not confirm:
        return

    # 删除插件目录
    import shutil

    shutil.rmtree(plugin_dir)
    click.echo(success(f"Plugin {name} removed successfully!"))


def echo_plugins():
    """列出所有可用插件

    显示本地和已安装的插件列表。
    """
    cwd = Path(os.getcwd())
    plugins_dir = cwd / "plugins"
    plugins = []
    stdout = stdout_run_proc(["uv", "run", "pip", "freeze"])
    freeze_str = [
        "(Package) " + (i.split("=="))[0]
        for i in (stdout).split("\n")
        if i.startswith("nonebot-plugin") or i.startswith("amrita-plugin")
    ]
    plugins.extend(freeze_str)

    if not plugins_dir.exists():
        click.echo(error("Not in an Amrita project directory."))
        return

    if not plugins_dir.is_dir():
        click.echo(error("Plugins directory is not a directory."))
        return

    plugins.extend(
        [
            "(Local) " + item.name.replace(".py", "")
            for item in plugins_dir.iterdir()
            if (
                not (item.name.startswith("-") or item.name.startswith("_"))
                and (item.is_dir() or item.name.endswith(".py"))
            )
        ]
    )

    if not plugins:
        click.echo(info("No plugins found."))
        return

    click.echo(success("Available plugins:"))
    for pl in plugins:
        click.echo(f"  - {pl}")


@plugin.command()
def list():
    """List all plugins.

    列出所有插件。
    """
    echo_plugins()
