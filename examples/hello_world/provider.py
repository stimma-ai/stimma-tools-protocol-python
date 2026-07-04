"""
Test STP Provider

A test provider that demonstrates the stimma-tools-protocol framework.
Provides text-to-image and image-to-image test tools.
"""

import asyncio
import io
from PIL import Image, ImageDraw, ImageFont
from stimma_tools_protocol import (
    tool,
    ToolParameter,
    Provider,
    ProviderConfig,
    run_provider,
    setup_logging,
    create_argument_parser,
)
from stimma_tools_protocol.provider import ExecutionContext


def render_text_to_image(text: str, width: int = 512, height: int = 512) -> bytes:
    """Render text onto a PNG image."""
    # Create image with dark background
    img = Image.new("RGB", (width, height), color=(30, 30, 40))
    draw = ImageDraw.Draw(img)

    # Try to use a nice font, fall back to default
    font_size = 24
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", font_size)
    except (OSError, IOError):
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", font_size)
        except (OSError, IOError):
            font = ImageFont.load_default()

    # Word wrap the text
    margin = 20
    max_width = width - 2 * margin
    lines = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current_line = words[0]
        for word in words[1:]:
            test_line = current_line + " " + word
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if bbox[2] - bbox[0] <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        lines.append(current_line)

    # Draw text
    y = margin
    for line in lines:
        draw.text((margin, y), line, fill=(200, 200, 220), font=font)
        y += font_size + 4
        if y > height - margin:
            break

    # Convert to PNG bytes
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


# Text-to-image test tool
@tool(
    slug="t2i-test",
    display_name="T2I Test Tool",
    task_types="text-to-image",
    description="Test tool for text-to-image - renders prompt text as an image.",
    parameters=[
        ToolParameter(
            name="prompt",
            type="string",
            description="Text to render",
            required=True,
        ),
        ToolParameter(
            name="uppercase",
            type="boolean",
            description="Convert text to uppercase",
            default=False,
        ),
        ToolParameter(
            name="width",
            type="integer",
            description="Image width",
            default=512,
            minimum=128,
            maximum=2048,
        ),
        ToolParameter(
            name="height",
            type="integer",
            description="Image height",
            default=512,
            minimum=128,
            maximum=2048,
        ),
    ],
)
async def t2i_test_tool(
    context: ExecutionContext,
    parameters: dict,
) -> dict:
    """
    Text-to-image test tool - renders text as an image.
    """
    text = parameters.get("prompt", "Hello World!")
    uppercase = parameters.get("uppercase", False)
    width = parameters.get("width", 512)
    height = parameters.get("height", 512)

    await context.report_progress(0.0)

    if uppercase:
        text = text.upper()

    await context.report_progress(0.3)

    # Render to image
    png_data = render_text_to_image(text, width, height)

    await context.report_progress(0.8)

    # Upload as PNG
    asset_id = await context.assets.upload(png_data, extension=".png")

    await context.report_progress(1.0)

    return {"asset_id": asset_id}


# Image edit test tool
@tool(
    slug="edit-test",
    display_name="Edit Test Tool",
    task_types="image-to-image",
    description="Test tool for image-to-image - converts input image to grayscale.",
    parameters=[
        ToolParameter(
            name="prompt",
            type="string",
            description="Edit instruction (ignored by this test tool)",
            required=True,
        ),
        ToolParameter(
            name="input_images",
            type="array",
            description="Input images to process",
            required=True,
        ),
        ToolParameter(
            name="invert",
            type="boolean",
            description="Invert the grayscale image",
            default=False,
        ),
    ],
)
async def edit_test_tool(
    context: ExecutionContext,
    parameters: dict,
) -> dict:
    """
    Image edit test tool - converts image to grayscale.
    """
    await context.report_progress(0.0)

    # Get input images array
    input_images = parameters.get("input_images", [])
    if not input_images:
        raise ValueError("No input images provided")

    # Process first image (for this test tool)
    input_value = input_images[0]

    # Check if it's a data URI (inline base64) or a file path/asset_id
    if input_value.startswith("data:"):
        import base64
        # Parse data URI: "data:<mime_type>;base64,<data>"
        header, b64_data = input_value.split(",", 1)
        image_data = base64.b64decode(b64_data)
    else:
        # It's an asset ID - download it
        image_data = await context.assets.download(input_value)

    await context.report_progress(0.3)

    # Load and convert to grayscale
    img = Image.open(io.BytesIO(image_data))
    gray_img = img.convert("L")

    await context.report_progress(0.6)

    # Optionally invert
    if parameters.get("invert", False):
        from PIL import ImageOps
        gray_img = ImageOps.invert(gray_img)

    # Convert back to RGB for output
    output_img = gray_img.convert("RGB")

    await context.report_progress(0.8)

    # Save and upload
    buffer = io.BytesIO()
    output_img.save(buffer, format="PNG")
    asset_id = await context.assets.upload(buffer.getvalue(), extension=".png")

    await context.report_progress(1.0)

    return {"asset_id": asset_id}


def main():
    """Main entry point for the test provider."""
    parser = create_argument_parser(description="Test STP Provider")
    args = parser.parse_args()

    setup_logging(args.log_level, "stp_test")

    config = ProviderConfig(
        provider_id="stp-test",
        provider_name="STP Test Provider",
        server="stp-test/1.0.0",
        max_concurrent=2,
        supports_cancel=True,
    )

    from stimma_tools_protocol.transport import StdioTransport

    provider = Provider(
        config=config,
        transport=StdioTransport(),
    )

    asyncio.run(run_provider(provider, args))


if __name__ == "__main__":
    main()
