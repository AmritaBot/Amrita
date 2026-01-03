import sys
from collections.abc import Callable
from functools import wraps

import click

import amrita
from amrita.cli import check_optional_dependency, error


def require_full_depencies(func: Callable):
    def wrapper(*args, **kwargs):
        if not check_optional_dependency(quiet=True):
            click.echo(error("请使用 `uv add amrita[full]` 安装完整的可选依赖。"))
            sys.exit(1)
        return func(*args, **kwargs)

    return wrapper


def require_init(func: Callable):
    @wraps(func)
    def wrapper(*args, **kwargs):
        amrita.init()
        amrita.load_plugins()
        return func(*args, **kwargs)

    return wrapper
