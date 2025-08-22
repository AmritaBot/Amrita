from importlib import metadata

__version__ = "unknown"

try:
    __version__ = metadata.version("amrita")
except metadata.PackageNotFoundError:
    pass


def get_amrita_version():
    return __version__
