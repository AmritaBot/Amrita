import os
from re import sub
import signal
import subprocess
import sys
from importlib import metadata
from pathlib import Path

from aiofiles import stdout
import click
import colorama
import toml
from colorama import Fore, Style
from pydantic import BaseModel, Field

# 处理相对导入问题
try:
    from .resource import DOTENV, GITIGNORE, README
except ImportError:
    # 当直接运行文件时，添加src目录到sys.path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from amrita.resource import DOTENV, GITIGNORE, README


# 全局变量用于跟踪子进程
_subprocesses: list[subprocess.Popen] = []


def _cleanup_subprocesses():
    """清理所有子进程"""
    click.echo(warn("Exiting......"))
    for proc in _subprocesses:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:  # noqa: PERF203
            proc.kill()
        except ProcessLookupError:
            pass  # 进程已经结束
    _subprocesses.clear()


def _signal_handler(signum, frame):
    """信号处理函数"""
    _cleanup_subprocesses()
    sys.exit(0)


# 注册信号处理函数
signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)


class Pyproject(BaseModel):
    name: str
    description: str = ""
    version: str = "0.1.0"
    dependencies: list[str] = Field(default_factory=lambda: ["amrita[full]>=0.1.0"])
    readme: str = "README.md"
    requires_python: str = ">=3.10, <4.0"


class NonebotTool(BaseModel):
    pass


class AmritaTool(BaseModel):
    plugins: list[str] = Field(default_factory=list)


class Tool(BaseModel):
    nonebot: NonebotTool = NonebotTool()
    amrita: AmritaTool = AmritaTool()


class PyprojectFile(BaseModel):
    project: Pyproject
    tool: Tool = Tool()


def check_optional_dependency():
    """检测amrita[full]可选依赖是否已安装"""
    try:
        proc = subprocess.Popen(
            ["uv", "pip", "show", "jieba"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _subprocesses.append(proc)
        try:
            proc.communicate(timeout=10)
            return proc.returncode == 0
        except subprocess.TimeoutExpired:
            proc.kill()
            return False
        finally:
            if proc in _subprocesses:
                _subprocesses.remove(proc)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def install_optional_dependency():
    """安装amrita[full]可选依赖"""
    try:
        proc = subprocess.Popen(
            ["uv", "add", "amrita[full]"],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        _subprocesses.append(proc)
        try:
            return_code = proc.wait()
            if return_code != 0:
                raise subprocess.CalledProcessError(
                    return_code, ["uv", "add", "amrita[full]"]
                )
            return True
        except KeyboardInterrupt:
            _cleanup_subprocesses()
            sys.exit(0)
        finally:
            if proc in _subprocesses:
                _subprocesses.remove(proc)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        click.echo(
            error(
                f"Failed to install amrita[full] dependency: {e}, try to install manually by 'uv add amrita[full]'"
            )
        )
        return False


def check_nb_cli_available():
    """检查nb-cli是否可用"""
    try:
        proc = subprocess.Popen(
            ["nb", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        _subprocesses.append(proc)
        try:
            proc.communicate(timeout=10)
            return proc.returncode == 0
        except subprocess.TimeoutExpired:
            proc.kill()
            return False
        finally:
            if proc in _subprocesses:
                _subprocesses.remove(proc)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def warn(message: str):
    return f"{Fore.YELLOW}[!]{Style.RESET_ALL} {message}"


def info(message: str):
    return f"{Fore.GREEN}[+]{Style.RESET_ALL} {message}"


def error(message: str):
    return f"{Fore.RED}[-]{Style.RESET_ALL} {message}"


def question(message: str):
    return f"{Fore.BLUE}[?]{Style.RESET_ALL} {message}"


def success(message: str):
    return f"{Fore.GREEN}[+]{Style.RESET_ALL} {message}"


@click.group()
def cli():
    """Amrita CLI - CLI for PROJ.AmritaBot"""
    pass


@cli.command()
def version():
    """Print the version number."""
    try:
        version = metadata.version("amrita")
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
def check_dependencies():
    """Check dependencies."""
    click.echo(info("Checking dependencies..."))

    # 检查uv是否可用
    try:
        proc = subprocess.Popen(
            ["uv", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        _subprocesses.append(proc)
        try:
            proc.communicate(timeout=10)
            if proc.returncode == 0:
                click.echo(success("uv is available"))
            else:
                click.echo(error("uv is not available. Please install uv first."))
                return False
        except subprocess.TimeoutExpired:
            proc.kill()
            click.echo(error("uv is not available. Please install uv first."))
            return False
        finally:
            if proc in _subprocesses:
                _subprocesses.remove(proc)
    except (subprocess.CalledProcessError, FileNotFoundError):
        click.echo(error("uv is not available. Please install uv first."))
        return False

    # 检查amrita[full]依赖
    if check_optional_dependency():
        click.echo(success("Dependencies checked successfully!"))
        return True
    else:
        click.echo(error("Dependencies has problems"))
        fix: bool = click.confirm(question("Do you want to fix it?"))
        if fix:
            return install_optional_dependency()
        return False


@cli.command()
@click.option("--project-name", "-p", help="Project name")
@click.option("--description", "-d", help="Project description")
@click.option(
    "--python-version", "-py", help="Python version requirement", default=">=3.10, <4.0"
)
@click.option("--this-dir", "-t", is_flag=True, help="Use current directory")
def create(project_name, description, python_version, this_dir):
    """Create a new project."""
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
    with open(project_dir / ".env", "w") as f:
        f.write(DOTENV)
    with open(project_dir / ".gitignore", "w") as f:
        f.write(GITIGNORE)
    with open(project_dir / "README.md", "w") as f:
        f.write(README.format(project_name=project_name))

    # 安装依赖
    click.echo(info("Installing dependencies..."))
    if not install_optional_dependency():
        click.echo(error("Failed to install dependencies."))
        return

    click.echo(success(f"Project {project_name} created successfully!"))
    click.echo(info("Next steps:"))
    click.echo(info(f"  cd {project_name if not this_dir else '.'}"))
    click.echo(info("  amrita run"))


@cli.command()
@click.option(
    "--run", "-r", is_flag=True, help="Run the project without installing dependencies."
)
def run(run: bool):
    """Run the project."""
    if run:
        try:
            from amrita import bot

            bot.run()
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

    # 使用Popen替代run以便更好地控制子进程
    proc = subprocess.Popen(cmd)
    _subprocesses.append(proc)
    try:
        proc.wait()
    except KeyboardInterrupt:
        _cleanup_subprocesses()
        sys.exit(0)
    finally:
        if proc in _subprocesses:
            _subprocesses.remove(proc)


@cli.command()
@click.option("--description", "-d", help="Project description")
def init(description):
    """Initialize current directory as an Amrita project."""
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

    with open(cwd / "pyproject.toml", "w") as f:
        f.write(toml.dumps(data))

    # 创建其他项目文件
    with open(cwd / ".env", "w") as f:
        f.write(DOTENV)
    with open(cwd / ".gitignore", "w") as f:
        f.write(GITIGNORE)
    with open(cwd / "README.md", "w") as f:
        f.write(README.format(project_name=project_name))

    # 安装依赖
    click.echo(info("Installing dependencies..."))
    if not install_optional_dependency():
        click.echo(error("Failed to install dependencies."))
        return

    click.echo(success("Project initialized successfully!"))
    click.echo(info("Next steps: amrita run"))


@click.group()
def plugin():
    """Manage plugins."""
    pass


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

        # 显示插件信息
        plugins_dir = Path("plugins")
        if plugins_dir.exists() and plugins_dir.is_dir():
            plugins = [item.name for item in plugins_dir.iterdir() if item.is_dir()]
            if plugins:
                click.echo("  Plugins:")
                for plugin in plugins:
                    click.echo(f"    - {plugin}")

    except Exception as e:
        click.echo(error(f"Error reading project info: {e}"))


@cli.command()
@click.argument("nb_args", nargs=-1)
def nb(nb_args):
    """Run nb-cli commands directly."""
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
        proc = subprocess.Popen(
            ["nb", *list(nb_args)],
            stdout=sys.stdout,
            stderr=sys.stderr,
            stdin=sys.stdin,
        )
        _subprocesses.append(proc)
        try:
            return_code = proc.wait()
            if return_code != 0:
                raise subprocess.CalledProcessError(return_code, ["nb", *list(nb_args)])
        except KeyboardInterrupt:
            _cleanup_subprocesses()
            sys.exit(0)
        finally:
            if proc in _subprocesses:
                _subprocesses.remove(proc)
    except subprocess.CalledProcessError as e:
        click.echo(error(f"nb-cli command failed with exit code {e.returncode}"))


# 添加plugin命令组到主cli组
cli.add_command(plugin)


def main():
    colorama.init()
    cli()


if __name__ == "__main__":
    main()
