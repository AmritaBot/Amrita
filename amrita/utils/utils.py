from importlib import metadata

__version__ = "unknown"
__core_version__ = metadata.version("amrita-core")

try:
    __version__ = metadata.version("amrita")
except metadata.PackageNotFoundError:
    pass


def get_amrita_version():
    return __version__


def get_core_version():
    return __core_version__
