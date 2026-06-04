"""
Runtime and CLI for STP providers.

Handles:
- Command-line argument parsing
- Logging setup (stderr only)
- Parent PID watcher for stdio mode
- Graceful shutdown
- Config file loading
"""

import argparse
import asyncio
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Optional, Type, Callable
import yaml

from stimma_tools_protocol.provider import Provider, ProviderConfig
from stimma_tools_protocol.transport import Transport, StdioTransport, WebSocketTransport
from stimma_tools_protocol.assets import AssetManager, FilesystemAssetManager


def setup_logging(level: str = "INFO", name: Optional[str] = None) -> logging.Logger:
    """
    Set up logging to stderr only.

    IMPORTANT: In stdio mode, stdout is used for JSON-RPC communication.
    All logging MUST go to stderr.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        name: Logger name (defaults to root logger)

    Returns:
        Configured logger
    """
    # Configure root logger to use stderr
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    logger = logging.getLogger(name)
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Also configure stimma_tools_protocol loggers
    stimma_logger = logging.getLogger("stimma_tools_protocol")
    if not stimma_logger.handlers:
        stimma_logger.addHandler(handler)
        stimma_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    return logger


def load_config(config_path: str) -> dict:
    """
    Load configuration from a YAML file.

    Args:
        config_path: Path to the config file

    Returns:
        Configuration dictionary
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path) as f:
        return yaml.safe_load(f) or {}


class ParentProcessWatcher:
    """
    Watches the parent process and triggers shutdown if it dies.

    This is important for stdio mode where the provider is a subprocess.
    If the parent (Stimma) dies unexpectedly, the provider should also exit.
    """

    def __init__(self, on_parent_exit: Callable[[], None]):
        self._on_parent_exit = on_parent_exit
        self._task: Optional[asyncio.Task] = None
        self._parent_pid = os.getppid()

    def start(self) -> None:
        """Start watching the parent process."""
        self._task = asyncio.create_task(self._watch())

    async def stop(self) -> None:
        """Stop watching."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _watch(self) -> None:
        """Watch loop - check if parent is still alive every second."""
        while True:
            try:
                # Check if parent process still exists
                # os.kill with signal 0 checks existence without sending signal
                os.kill(self._parent_pid, 0)
            except (OSError, ProcessLookupError):
                # Parent process is gone
                logging.getLogger(__name__).warning(
                    f"Parent process {self._parent_pid} died, shutting down"
                )
                self._on_parent_exit()
                return

            await asyncio.sleep(1.0)


def create_argument_parser(description: str = "STP Provider") -> argparse.ArgumentParser:
    """
    Create the standard argument parser for STP providers.

    Args:
        description: Description for --help output

    Returns:
        Configured argument parser
    """
    parser = argparse.ArgumentParser(description=description)

    # Transport mode (mutually exclusive)
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--stdio",
        action="store_true",
        help="Run in stdio mode (for Stimma subprocess)",
    )
    mode_group.add_argument(
        "--websocket",
        action="store_true",
        help="Run in WebSocket server mode",
    )

    # WebSocket options
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind address (default: 127.0.0.1; pass 0.0.0.0 to accept connections from other machines)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="WebSocket server port (default: 8765)",
    )
    parser.add_argument(
        "--auth-token",
        help="Bearer token for WebSocket authentication",
    )

    # Config
    parser.add_argument(
        "--config",
        "-c",
        help="Path to configuration file (YAML)",
    )

    # Logging
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level (default: INFO)",
    )

    return parser


async def run_provider(
    provider: Provider,
    args: Optional[argparse.Namespace] = None,
    transport: Optional[Transport] = None,
    asset_manager: Optional[AssetManager] = None,
) -> None:
    """
    Run an STP provider with the given configuration.

    This is the main entry point for running a provider. It handles:
    - Transport setup based on args
    - Asset manager setup
    - Parent PID watching (stdio mode)
    - Signal handling
    - Running the provider until stdin closes

    Args:
        provider: The Provider instance to run
        args: Parsed command-line arguments (from create_argument_parser)
        transport: Optional pre-configured transport
        asset_manager: Optional pre-configured asset manager
    """
    logger = logging.getLogger(__name__)

    # Set up signal handlers - just exit cleanly
    loop = asyncio.get_event_loop()

    def handle_signal(sig):
        logger.info(f"Received signal {sig.name}, exiting...")
        os._exit(0)

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: handle_signal(s))

    # Parent watcher callback - just exit
    def on_parent_exit():
        logger.info("Parent process died, exiting...")
        os._exit(0)

    parent_watcher: Optional[ParentProcessWatcher] = None

    try:
        # Set up transport if not provided
        if transport is None:
            if args is None:
                raise ValueError("Either transport or args must be provided")

            if args.stdio:
                transport = StdioTransport()
                # Start parent watcher for stdio mode
                parent_watcher = ParentProcessWatcher(on_parent_exit)
                parent_watcher.start()
            else:
                transport = WebSocketTransport(
                    host=args.host,
                    port=args.port,
                    auth_token=args.auth_token,
                )

        # Set up asset manager if not provided
        if asset_manager is None:
            if args and args.stdio:
                # Use filesystem assets from ASSET_PATH env var
                asset_manager = FilesystemAssetManager()
            # For websocket, asset manager is set up after registration

        # Create a new provider with the transport
        from stimma_tools_protocol.tool import get_registry

        actual_provider = Provider(
            config=provider.config,
            transport=transport,
            tool_registry=get_registry(),
        )

        # Start and run the provider until stdin closes
        await actual_provider.start(asset_manager)
        await actual_provider.run()

    except asyncio.CancelledError:
        # Normal shutdown (EOF on stdin)
        pass
    except Exception as e:
        logger.exception(f"Provider error: {e}")
        raise


def main(
    provider_class: Type[Provider],
    description: str = "STP Provider",
) -> None:
    """
    Main entry point for an STP provider CLI.

    This creates the argument parser, parses args, sets up logging,
    and runs the provider.

    Args:
        provider_class: The Provider class to instantiate
        description: Description for --help
    """
    parser = create_argument_parser(description)
    args = parser.parse_args()

    # Set up logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    # Load config if provided
    config = {}
    if args.config:
        try:
            config = load_config(args.config)
            logger.info(f"Loaded config from {args.config}")
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            sys.exit(1)

    # Create provider config
    provider_config = ProviderConfig(
        provider_id=config.get("provider_id", "default"),
        provider_name=config.get("provider_name", description),
        server=config.get("server"),
        max_concurrent=config.get("max_concurrent", 1),
        supports_cancel=config.get("supports_cancel", True),
    )

    # Create dummy provider for config (actual one created in run_provider)
    provider = Provider(
        config=provider_config,
        transport=StdioTransport(),  # Placeholder
    )

    # Run
    try:
        asyncio.run(run_provider(provider, args))
    except KeyboardInterrupt:
        logger.info("Interrupted")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)
