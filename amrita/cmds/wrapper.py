import sys
from collections.abc import Callable

import click

from amrita.cli import check_optional_dependency, error


def cwd_to_module(func: Callable):
    def wrapper(*args, **kwargs):
        if "." not in sys.path:
            sys.path.insert(0, ".")

    return wrapper


def require_full_depencies(func: Callable):
    def wrapper(*args, **kwargs):
        if not check_optional_dependency(quiet=True):
            click.echo(
                error("请使用 `uv add install amrita[full]` 安装完整的可选依赖。")
            )
            sys.exit(1)
        return func(*args, **kwargs)

    return wrapper
