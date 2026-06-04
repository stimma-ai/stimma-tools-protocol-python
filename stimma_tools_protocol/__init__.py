"""
Stimma Tools Protocol (STP) Framework

A Python framework for building STP-compliant tool providers.
"""

from stimma_tools_protocol.protocol import (
    JsonRpcRequest,
    JsonRpcResponse,
    JsonRpcNotification,
    JsonRpcError,
    STPError,
)
from stimma_tools_protocol.provider import Provider, ProviderConfig
from stimma_tools_protocol.tool import tool, Tool, ToolParameter, ToolDescriptor, Group, Param
from stimma_tools_protocol.transport import Transport, StdioTransport, WebSocketTransport
from stimma_tools_protocol.assets import AssetManager, LocalAssetServer, FilesystemAssetManager
from stimma_tools_protocol.runner import run_provider, setup_logging, create_argument_parser


def was_provided(params: dict, key: str) -> bool:
    """Check if a parameter was explicitly provided in the request.

    Use this to distinguish between "not provided" (will have default applied)
    and "explicitly set" (even if set to the default value).

    Args:
        params: The parameters or input dict passed to the tool
        key: The parameter name to check

    Returns:
        True if the key was in the original request, False if it was filled by defaults
    """
    provided_keys = params.get("_provided_keys", set())
    return key in provided_keys


__version__ = "0.1.0"

__all__ = [
    # Protocol
    "JsonRpcRequest",
    "JsonRpcResponse",
    "JsonRpcNotification",
    "JsonRpcError",
    "STPError",
    # Provider
    "Provider",
    "ProviderConfig",
    # Tools
    "tool",
    "Tool",
    "ToolParameter",
    "ToolDescriptor",
    # Layout DSL
    "Group",
    "Param",
    # Transport
    "Transport",
    "StdioTransport",
    "WebSocketTransport",
    # Assets
    "AssetManager",
    "LocalAssetServer",
    "FilesystemAssetManager",
    # Runner
    "run_provider",
    "setup_logging",
    "create_argument_parser",
    # Utilities
    "was_provided",
]
