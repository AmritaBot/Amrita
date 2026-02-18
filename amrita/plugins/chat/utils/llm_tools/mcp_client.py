"""为了兼容，保留了这个文件，但不再使用它。"""

import warnings

warnings.warn(
    "This module is deprecated and will be removed in a future version(1.2.0).Please import from `amrita_core.tools.mcp` instead.",
    DeprecationWarning,
    stacklevel=2,
)

# 模块的其余部分...
from amrita_core.tools.mcp import (
    MCP_SERVER_SCRIPT_TYPE,
    ClientManager,
    MCPClient,
    MultiClientManager,
)

__all__ = ["MCP_SERVER_SCRIPT_TYPE", "ClientManager", "MCPClient", "MultiClientManager"]
