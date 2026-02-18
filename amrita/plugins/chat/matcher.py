import warnings

warnings.warn(
    "This module is deprecated and will be removed in a future version(1.2.0).Please import from `amrita_core` instead.",
    DeprecationWarning,
    stacklevel=2,
)
from amrita_core.hook.matcher import (
    ChatException,
    FunctionData,
    Matcher,
    MatcherManager,
)

__all__ = ["ChatException", "FunctionData", "Matcher", "MatcherManager"]
