import os
import subprocess
import sys
from pathlib import Path

import click

from amrita.cli import (
    _cleanup_subprocesses,
    _subprocesses,
    error,
    info,
    nb,
    plugin,
    question,
    success,
    warn,
)


@plugin.command()
@click.argument("name")
def install(name: str):
    """Install a plugin."""
    nb(["plugin", "install", name])


@plugin.command()
@click.argument("name")
def new(name: str):
    """Create a new plugin."""
    cwd = Path(os.getcwd())
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
        f.write(f"""from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent

# Register your commands here
{name.replace("-", "_")} = on_command("{name}")

@{name.replace("-", "_")}.handle()
async def handle_function(event: MessageEvent):
    await {name.replace("-", "_")}.finish("Hello from {name}!")
""")

    # 创建配置文件
    with open(plugin_dir / "config.py", "w") as f:
        f.write(f"""# Configuration for {name} plugin

# Add your configuration here
""")

    click.echo(success(f"Plugin {name} created successfully!"))


@plugin.command()
@click.argument("name")
def remove(name: str):
    """Remove a plugin."""
    cwd = Path(os.getcwd())
    plugin_dir = cwd / "plugins" / name

    if not plugin_dir.exists():
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


@plugin.command()
def list_plugins():
    """List all plugins."""
    cwd = Path(os.getcwd())
    plugins_dir = cwd / "plugins"
    plugins = []
    proc = subprocess.Popen(
        ["uv", "run", "pip", "freeze"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, _ = proc.communicate()
    _subprocesses.append(proc)
    try:
        return_code = proc.wait()
        if return_code != 0:
            raise subprocess.CalledProcessError(
                return_code, ["uv", "run", "pip", "freeze"]
            )
    except KeyboardInterrupt:
        _cleanup_subprocesses()
        sys.exit(0)
    finally:
        if proc in _subprocesses:
            _subprocesses.remove(proc)
    freeze_str = [
        "(Package) " + (i.split("=="))[0]
        for i in (
            stdout.decode("utf-8" if "linux" in sys.platform.lower() else "gbk")
        ).split("\n")
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
