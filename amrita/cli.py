"""Amrita CLI工具模块

该模块提供了Amrita项目的命令行界面工具，用于项目管理、依赖检查、插件管理等功能。
"""

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
    """运行子进程并等待其完成

    Args:
        cmd: 要执行的命令列表
        stdin: 标准输入流
        stdout: 标准输出流
        stderr: 标准错误流
        **kwargs: 其他传递给Popen的参数

    Returns:
        进程的返回码

    Raises:
        subprocess.CalledProcessError: 当进程返回非零退出码时
    """
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
    """运行子进程并返回标准输出

    Args:
        cmd: 要执行的命令列表

    Returns:
        进程的标准输出内容（字符串格式）

    Raises:
        subprocess.CalledProcessError: 当进程返回非零退出码时
    """
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
    """清理所有子进程

    终止所有正在运行的子进程，首先尝试优雅地终止，超时后强制杀死。
    """
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
    """信号处理函数

    当接收到终止信号时，清理所有子进程并退出程序。

    Args:
        signum: 信号编号
        frame: 当前堆栈帧
    """
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
    """检测amrita[full]可选依赖是否已安装

    Args:
        is_self: 是否在当前环境中直接检查
        with_details: 是否返回详细信息（缺失的依赖列表）

    Returns:
        如果with_details为True，返回(状态, 缺失依赖列表)元组；
        否则只返回状态布尔值
    """
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
    """在不使用虚拟环境的情况下安装可选依赖

    Returns:
        安装是否成功
    """
    try:
        run_proc(["pip", "install", "amrita[full]"])
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        click.echo(error("pip run failed."))
        return False


def install_optional_dependency() -> bool:
    """安装amrita[full]可选依赖

    使用uv工具安装amrita的完整依赖包。

    Returns:
        安装是否成功
    """
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
    """检查nb-cli是否可用

    Returns:
        nb-cli是否可用
    """
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
    """返回带警告颜色的消息

    Args:
        message: 要着色的消息文本

    Returns:
        带颜色编码的警告消息
    """
    return f"{Fore.YELLOW}[!]{Style.RESET_ALL} {message}"


def info(message: str):
    """返回带信息颜色的消息

    Args:
        message: 要着色的消息文本

    Returns:
        带颜色编码的信息消息
    """
    return f"{Fore.GREEN}[+]{Style.RESET_ALL} {message}"


def error(message: str):
    """返回带错误颜色的消息

    Args:
        message: 要着色的消息文本

    Returns:
        带颜色编码的错误消息
    """
    return f"{Fore.RED}[-]{Style.RESET_ALL} {message}"


def question(message: str):
    """返回带问题颜色的消息

    Args:
        message: 要着色的消息文本

    Returns:
        带颜色编码的问题消息
    """
    return f"{Fore.BLUE}[?]{Style.RESET_ALL} {message}"


def success(message: str):
    """返回带成功颜色的消息

    Args:
        message: 要着色的消息文本

    Returns:
        带颜色编码的成功消息
    """
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
    """CLI主函数"""
    colorama.init()
    cli()


if __name__ == "__main__":
    main()
