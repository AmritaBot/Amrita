import os
import subprocess
import sys
from importlib import import_module, metadata
from pathlib import Path

import click
import colorama
import toml
from colorama import Fore
from pydantic import BaseModel

# 处理相对导入问题
try:
    from .resource import DOTENV, GITIGNORE, README
except ImportError:
    # 当直接运行文件时，添加src目录到sys.path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from amrita.resource import DOTENV, GITIGNORE, README


class Pyproject(BaseModel):
    name: str
    description: str
    version: str
    dependencies: list[str] = ["amrita[full]>=0.1.0"]
    readme: str = "README.md"


class NonebotTool(BaseModel): ...


class AmritaTool(BaseModel):
    plugins: list[str] = []


class Tool(BaseModel):
    nonebot: NonebotTool = NonebotTool()
    amrita: AmritaTool = AmritaTool()


class PyprojectFile(BaseModel):
    project: Pyproject
    tool: Tool = Tool()


def check_optional_dependency():
    """检测amrita[full]可选依赖是否已安装"""
    try:
        subprocess.check_output(["uv","pip", "show", "jieba"])
        return True
    except subprocess.CalledProcessError:
        return False


def install_optional_dependency():
    """安装amrita[full]可选依赖"""
    try:
        subprocess.run(
            ["uv", "add", "amrita[full]"],
            check=True,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        return True
    except subprocess.CalledProcessError as e:
        click.echo(
            error(
                f"Failed to install amrita[full] dependency: {e.stderr},try to install manually by 'uv add amrita[full]'"
            )
        )
        return False


def warn(message: str):
    return f"{Fore.YELLOW}[!]{Fore.WHITE} {message}"


def info(message: str):
    return f"{Fore.GREEN}[+]{Fore.WHITE} {message}"


def error(message: str):
    return f"{Fore.RED}[-]{Fore.YELLOW} {message}"


def question(message: str):
    return f"{Fore.BLUE}[?]{Fore.WHITE} {message}"


def success(message: str):
    return f"{Fore.GREEN}[+]{Fore.WHITE} {message}"


@click.group()
def cli():
    pass


@cli.command()
def version():
    """Print the version number."""
    version = "unknown"
    try:
        version = metadata.version("amrita")
    except metadata.PackageNotFoundError:
        pass
    click.echo(version)


@cli.command()
def check_dependencies():
    """Check dependencies."""
    click.echo(warn("Checking dependencies..."))
    if check_optional_dependency():
        click.echo(success("Dependencies checked successfully!"))
    else:
        click.echo(error("Dependencies has problems"))
        fix:bool = click.confirm(question("Do you want to fix it?"))
        if fix:
            install_optional_dependency()


@cli.command()
@click.option("--project-name-arg", "-p", help="Project name")
@click.option("--this-dir", "-t", help="This directory", is_flag=True)
def create(project_name_arg, this_dir):
    """Create a new project."""
    cwd = Path(os.getcwd())
    project_name = project_name_arg or click.prompt(question("Project name"), type=str)
    project_dir = cwd / project_name if not this_dir else cwd

    if project_dir.exists() and project_dir.is_dir() and list(project_dir.iterdir()):
        click.echo(warn(f"Project {project_name} already exists."))
        return
    click.echo(info(f"Creating project {project_name}..."))
    data = PyprojectFile(
        project=Pyproject(name=project_name, description="", version="0.1.0")
    ).model_dump()
    data["project"]["requires-python"] = ">=3.10, <4.0"

    with open(project_dir / "pyproject.toml", "w") as f:
        f.write(toml.dumps(data))
    with open(project_dir / ".env", "w") as f:
        f.write(DOTENV)
    with open(project_dir / ".gitignore", "w") as f:
        f.write(GITIGNORE)
    with open(project_dir / "README.md", "w") as f:
        f.write(README.format(project_name=project_name))
    os.makedirs(str(project_dir / "plugins"), exist_ok=True)

    # 新增依赖安装
    click.echo(warn("Installing dependencies..."))
    if not install_optional_dependency():
        click.echo(error("Failed to install dependencies."))
        return

    click.echo(success("Project created successfully!"))


@cli.command()
@click.option("--run","-r",is_flag=True,help="Run the project without installing dependencies.")
def run(run:bool):
    """Run the project."""
    if run:
        try:
            from amrita import bot

            bot.run()
        except ImportError as e:
            click.echo(f"{Fore.RED}[-]{Fore.WHITE} 缺失依赖: {e}")
            return
        except Exception as e:
            click.echo(f"{Fore.RED}[-]{Fore.WHITE} 运行错误: {e}")
            return
    if not os.path.exists("pyproject.toml"):
        click.echo(error("pyproject.toml not found"))
        return

    # 新增依赖检测和安装逻辑
    if not check_optional_dependency():
        click.echo(warn("Missing optional dependency 'full'"))
        if not install_optional_dependency():
            click.echo(error("Failed to install optional dependency 'full'"))
            return
    click.echo(info("Starting project"))
    subprocess.run(["uv","run","amrita","run","--run"])


@cli.command()
def init():
    """Initialize current directory as an Amrita project."""
    cwd = Path(os.getcwd())
    project_name = cwd.name

    if (cwd / "pyproject.toml").exists():
        click.echo(warn("Project already initialized."))
        return

    click.echo(info(f"Initializing project {project_name}..."))
    data = PyprojectFile(
        project=Pyproject(name=project_name, description="", version="0.1.0")
    ).model_dump()
    data["project"]["requires-python"] = ">=3.10, <4.0"

    with open(cwd / "pyproject.toml", "w") as f:
        f.write(toml.dumps(data))
    with open(cwd / ".env", "w") as f:
        f.write(DOTENV)
    with open(cwd / ".gitignore", "w") as f:
        f.write(GITIGNORE)
    with open(cwd / "README.md", "w") as f:
        f.write(README.format(project_name=project_name))
    os.makedirs(str(cwd / "plugins"), exist_ok=True)

    # 新增依赖安装
    click.echo(warn("Installing dependencies..."))
    if not install_optional_dependency():
        click.echo(error("Failed to install dependencies."))
        return

    click.echo(success("Project initialized successfully!"))


@click.group()
def plugin():
    """Manage plugins."""
    pass


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
        return

    os.makedirs(plugin_dir)
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

    # 新增依赖安装
    if not check_optional_dependency():
        click.echo(warn("Installing dependencies..."))
        if not install_optional_dependency():
            click.echo(error("Failed to install dependencies."))
            return

    click.echo(success(f"Plugin {name} created successfully!"))


@plugin.command()
def list():
    """List all plugins."""
    cwd = Path(os.getcwd())
    plugins_dir = cwd / "plugins"

    if not plugins_dir.exists():
        click.echo(error("Not in an Amrita project directory."))
        return

    if not plugins_dir.is_dir():
        click.echo(error("Plugins directory is not a directory."))
        return

    plugins = [item.name for item in plugins_dir.iterdir() if item.is_dir()]

    if not plugins:
        click.echo(info("No plugins found."))
        return

    click.echo(success("Available plugins:"))
    for plugin in plugins:
        click.echo(f"  - {plugin}")


@cli.command()
def proj_info():
    """Show project information."""
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

    except Exception as e:
        click.echo(error(f"Error reading project info: {e}"))


# 添加plugin命令组到主cli组
cli.add_command(plugin)


def main():
    colorama.init()
    cli()


if __name__ == "__main__":
    main()
