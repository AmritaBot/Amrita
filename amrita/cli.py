import signal
import subprocess
import sys
from typing import Literal, overload

import click
import colorama
from colorama import Fore, Style

from amrita.utils.dependencies import self_check_optional_dependency

# 全局变量用于跟踪子进程
_subprocesses: list[subprocess.Popen] = []


def run_proc(
    cmd: list[str], stdin=None, stdout=sys.stdout, stderr=sys.stderr, **kwargs
):
    proc = subprocess.Popen(
        cmd,
        stdout=stdout,
        stderr=stderr,
        stdin=stdin,
        **kwargs,
    )
    _subprocesses.append(proc)
    try:
        return_code = proc.wait()
        if return_code != 0:
            raise subprocess.CalledProcessError(
                return_code, cmd, output=proc.stderr.read() if proc.stderr else None
            )
    except KeyboardInterrupt:
        _cleanup_subprocesses()
        sys.exit(0)
    finally:
        if proc in _subprocesses:
            _subprocesses.remove(proc)


def stdout_run_proc(cmd: list[str]):
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, _ = proc.communicate()
    _subprocesses.append(proc)
    try:
        return_code = proc.wait()
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, cmd)
    except KeyboardInterrupt:
        _cleanup_subprocesses()
        sys.exit(0)
    finally:
        if proc in _subprocesses:
            _subprocesses.remove(proc)
    return stdout.decode("utf-8")


def _cleanup_subprocesses():
    """清理所有子进程"""
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


@overload
def check_optional_dependency(
    is_self: Literal[True], with_details: Literal[True]
) -> tuple[bool, list[str]]: ...


@overload
def check_optional_dependency(is_self: bool = False) -> bool: ...


def check_optional_dependency(
    is_self: bool = False, with_details: bool = False
) -> bool | tuple[bool, list[str]]:
    """检测amrita[full]可选依赖是否已安装"""
    if not is_self:
        try:
            run_proc(
                ["uv", "run", "amrita", "check-dependencies", "--self"],
                stdout=subprocess.PIPE,
            )
            return True
        except subprocess.CalledProcessError:
            return False
    else:
        status, missed = self_check_optional_dependency()
        if not status:
            click.echo(
                error(
                    "Some optional dependencies are missing. Please install them first."
                )
            )
            for pkg in missed:
                click.echo(f"- {pkg} was required, but it was not found.")
            click.echo(info("You can install them by running:\n  uv add amrita[full]"))
        if with_details:
            return status, missed
        return status


def install_optional_dependency_no_venv() -> bool:
    try:
        run_proc(["pip", "install", "amrita[full]"])
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        click.echo(error("pip run failed."))
        return False


def install_optional_dependency() -> bool:
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


@cli.group()
def plugin():
    """Manage plugins."""
    pass


cli.add_command(plugin)


def main():
    colorama.init()
    cli()


if __name__ == "__main__":
    main()
