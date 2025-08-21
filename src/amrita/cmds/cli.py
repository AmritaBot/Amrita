import importlib.metadata as metadata
import os
import subprocess
from pathlib import Path

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
    question,
    run_proc,
    stdout_run_proc,
    success,
    warn,
)
from ..resource import DOTENV, DOTENV_DEV, DOTENV_PROD, GITIGNORE, README


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
        stdout_run_proc(["uv", "--version"])
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
    if not (project_dir / ".env").exists():
        with open(project_dir / ".env", "w") as f:
            f.write(DOTENV)
    if not (project_dir / ".env.prod").exists():
        with open(project_dir / ".env.prod", "w"):
            f.write(DOTENV_PROD)
    if not (project_dir / ".env.dev").exists():
        with open(project_dir / ".env.dev", "w"):
            f.write(DOTENV_DEV)
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
def entry():
    """Generate a bot.py on current directory."""
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
    """Run the project."""
    if run:
        try:
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

    # 使用Popen替代run以便更好地控制子进程
    run_proc(cmd)


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
        run_proc(["nb", *list(nb_args)])
    except subprocess.CalledProcessError as e:
        click.echo(error(f"nb-cli command failed with exit code {e.returncode}"))
