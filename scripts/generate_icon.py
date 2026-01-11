"""Generate a simple Faceit-style icon for the system tray."""

from pathlib import Path

from PIL import Image, ImageDraw


def generate_icon():
    """Generate a simple orange 'F' icon (Faceit style)."""
    # Create 64x64 image with Faceit orange background
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw orange circle
    padding = 2
    draw.ellipse(
        [padding, padding, size - padding, size - padding],
        fill=(255, 85, 0, 255),  # Faceit orange
    )

    # Draw 'F' letter in white
    # Simple rectangle-based F
    f_left = 22
    f_top = 14
    f_width = 20
    f_height = 36
    bar_height = 6

    # Vertical bar
    draw.rectangle(
        [f_left, f_top, f_left + bar_height, f_top + f_height],
        fill=(255, 255, 255, 255),
    )

    # Top horizontal bar
    draw.rectangle(
        [f_left, f_top, f_left + f_width, f_top + bar_height],
        fill=(255, 255, 255, 255),
    )

    # Middle horizontal bar
    mid_y = f_top + f_height // 2 - bar_height // 2
    draw.rectangle(
        [f_left, mid_y, f_left + f_width - 4, mid_y + bar_height],
        fill=(255, 255, 255, 255),
    )

    # Save as ICO
    assets_dir = Path(__file__).parent.parent / "assets"
    assets_dir.mkdir(exist_ok=True)

    # Save in multiple sizes for ICO format
    icon_path = assets_dir / "icon.ico"
    img_16 = img.resize((16, 16), Image.Resampling.LANCZOS)
    img_32 = img.resize((32, 32), Image.Resampling.LANCZOS)
    img_48 = img.resize((48, 48), Image.Resampling.LANCZOS)

    img.save(
        icon_path,
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64)],
    )

    print(f"Icon saved to: {icon_path}")


if __name__ == "__main__":
    generate_icon()
