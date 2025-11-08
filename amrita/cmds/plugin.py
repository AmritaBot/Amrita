"""Amrita CLI插件管理模块

该模块实现了Amrita CLI的插件管理命令，包括插件的安装、创建、删除和列表查看等功能。
"""

import os
import subprocess
from pathlib import Path
from subprocess import CalledProcessError

import click
import toml

from amrita.cli import (
    error,
    get_package_metadata,
    info,
    plugin,
    question,
    run_proc,
    stdout_run_proc,
    success,
    warn,
)
from amrita.resource import EXAMPLE_PLUGIN, EXAMPLE_PLUGIN_CONFIG


def pypi_install(name: str):
    """从PyPI安装插件

    Args:
        name: 插件名称
    """
    name = name.replace("_", "-")
    click.echo(info("尝试直接从PyPI安装插件..."))
    metadata = get_package_metadata(name)
    if not metadata:
        click.echo(error("未找到包"))
        return
    click.echo(info(f"正在下载 {name}..."))
    try:
        run_proc(["uv", "add", name])
    except CalledProcessError:
        click.echo(error(f"安装 {name} 失败"))
        return
    click.echo(info("正在安装..."))
    with open("pyproject.toml", encoding="utf-8") as f:
        data = toml.load(f)
        if "nonebot" not in data["tool"]:
            data["tool"]["nonebot"] = {}
            data["tool"]["nonebot"]["plugins"] = []
        if name.replace("-", "_") not in data["tool"]["nonebot"]["plugins"]:
            data["tool"]["nonebot"]["plugins"].append(name.replace("-", "_"))
    with open("pyproject.toml", "w", encoding="utf-8") as f:
        toml.dump(data, f)
    click.echo(success(f"插件 {name} 已添加到 pyproject.toml 并成功安装。"))


@plugin.command()
@click.argument("name")
@click.option("--pypi", "-p", help="直接从PyPI安装", is_flag=True, default=False)
def install(name: str, pypi: bool):
    """安装插件。

    安装指定的插件。

    Args:
        name: 插件名称
        pypi: 是否直接从PyPI安装
    """
    cwd = Path(os.getcwd())
    if (cwd / "plugins" / name).exists():
        click.echo(warn(f"插件 {name} 已存在。"))
        return
    if pypi or name.replace("_", "-").startswith("amrita-plugin-"):
        pypi_install(name)
    else:
        try:
            run_proc(
                ["nb", "plugin", "install", name],
            )
        except Exception:
            click.echo(error(f"安装插件 {name} "))
            if click.confirm(question("您想要尝试从PyPI直接安装吗?")):
                return pypi_install(name)


@plugin.command()
@click.argument("name", default="")
def new(name: str):
    """创建新插件。

    创建一个新的插件。

    Args:
        name: 插件名称
    """
    cwd = Path(os.getcwd())
    if not name:
        name = click.prompt(question("插件名称"))
    plugins_dir = cwd / "plugins"

    if not plugins_dir.exists():
        click.echo(error("不在Amrita项目目录中。"))
        return

    plugin_dir = plugins_dir / name
    if plugin_dir.exists():
        click.echo(warn(f"插件 {name} 已存在。"))
        overwrite = click.confirm(question("您想要覆盖它吗?"), default=False)
        if not overwrite:
            return

    os.makedirs(plugin_dir, exist_ok=True)

    # 创建插件文件
    with open(plugin_dir / "__init__.py", "w", encoding="utf-8") as f:
        f.write(
            f"from . import {name.replace('-', '_')}\n\n__all__ = ['{name.replace('-', '_')}']\n"
        )

    with open(plugin_dir / f"{name.replace('-', '_')}.py", "w", encoding="utf-8") as f:
        f.write(EXAMPLE_PLUGIN.format(name=name.replace("-", "_")))

    # 创建配置文件
    with open(plugin_dir / "config.py", "w", encoding="utf-8") as f:
        f.write(EXAMPLE_PLUGIN_CONFIG.format(name=name.replace("-", "_")))

    click.echo(success(f"插件 {name} 创建成功!"))


@plugin.command()
@click.argument("name", default="")
def remove(name: str):
    """删除插件。

    删除指定的插件。

    Args:
        name: 插件名称
    """
    if not name:
        name = click.prompt(question("输入插件名称"))
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
        click.echo(error(f"插件 {name} 不存在。"))
        return

    confirm = click.confirm(question(f"您确定要删除插件 '{name}' 吗?"), default=False)
    if not confirm:
        return

    # 删除插件目录
    import shutil

    shutil.rmtree(plugin_dir)
    click.echo(success(f"插件 {name} 删除成功!"))


def echo_plugins():
    """列出所有可用插件

    显示本地和已安装的插件列表。
    """
    cwd = Path(os.getcwd())
    plugins_dir = cwd / "plugins"
    plugins = []
    stdout = stdout_run_proc(["uv", "run", "pip", "freeze"])
    freeze_str = [
        "(包) " + (i.split("=="))[0]
        for i in (stdout).split("\n")
        if i.startswith("nonebot-plugin") or i.startswith("amrita-plugin")
    ]
    plugins.extend(freeze_str)

    if not plugins_dir.exists():
        click.echo(error("不在Amrita项目目录中。"))
        return

    if not plugins_dir.is_dir():
        click.echo(error("插件目录不是一个目录。"))
        return

    plugins.extend(
        [
            "(本地) " + item.name.replace(".py", "")
            for item in plugins_dir.iterdir()
            if (
                not (item.name.startswith("-") or item.name.startswith("_"))
                and (item.is_dir() or item.name.endswith(".py"))
            )
        ]
    )

    if not plugins:
        click.echo(info("未找到插件。"))
        return

    click.echo(success("可用插件:"))
    for pl in plugins:
        click.echo(f"  - {pl}")


@plugin.command()
def list():
    """列出所有插件。

    列出所有插件。
    """
    echo_plugins()
