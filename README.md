# stimma-tools-protocol

Python framework for building Stimma Tool Protocol (STP) providers.

STP providers expose tools (image generation, editing, etc.) to the Stimma application over JSON-RPC. This library handles the protocol plumbing so you can focus on implementing tools.

## Installation

```bash
pip install stimma-tools-protocol
```

## Usage

```python
import asyncio
from stimma_tools_protocol import (
    tool, ToolParameter, Provider, ProviderConfig,
    run_provider, setup_logging, create_argument_parser,
)
from stimma_tools_protocol.provider import ExecutionContext


@tool(
    slug="my-tool",
    display_name="My Tool",
    task_type="text-to-image",
    parameters=[
        ToolParameter(name="prompt", type="string", required=True),
        ToolParameter(name="steps", type="integer", default=30),
    ],
)
async def my_tool(context: ExecutionContext, parameters: dict) -> dict:
    prompt = parameters["prompt"]
    steps = parameters["steps"]

    await context.report_progress(0.5)

    # Your generation logic here
    data = generate_image(prompt, steps)
    asset_id = await context.assets.upload(data, extension=".png")

    return {"asset_id": asset_id}


def main():
    parser = create_argument_parser(description="My Provider")
    args = parser.parse_args()
    setup_logging(args.log_level)

    config = ProviderConfig(
        provider_id="my-provider",
        provider_name="My Provider",
        max_concurrent=2,
    )

    from stimma_tools_protocol.transport import StdioTransport
    provider = Provider(config=config, transport=StdioTransport())
    asyncio.run(run_provider(provider, args))


if __name__ == "__main__":
    main()
```

## Running

```bash
# Stdio mode (Stimma spawns as subprocess)
python my_provider.py --stdio

# WebSocket mode (standalone server)
python my_provider.py --websocket --port 8765
```

## Features

- `@tool` decorator for defining tools with typed parameters
- `STANDARD_TASK_TYPES` export for recognized STP task types, including `video-to-video`
- Automatic JSON Schema generation
- Progress reporting
- Asset upload/download
- Stdio and WebSocket transports
- Job queuing with configurable concurrency
- Cancellation support

## Examples

See `examples/hello_world/` for a working provider.

## License

Apache 2.0
