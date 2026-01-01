from .cli import main as cli_main
from .cmds import main as cmd_main
from .cmds import plugin


def main(*args):
    cli_main(*args)


if __name__ == "__main__":
    main()

__all__ = ["cmd_main", "plugin"]
