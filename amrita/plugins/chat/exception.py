import warnings

warnings.warn(
    "This module is deprecated and will be removed in a future version(1.2.0).Please import from `amrita_core` instead.",
    DeprecationWarning,
    stacklevel=2,
)
from amrita_core.hook.exception import (
    BlockException,
    CancelException,
    MatcherException,
    PassException,
)

__all__ = [
    "BlockException",
    "CancelException",
    "MatcherException",
    "PassException",
]
