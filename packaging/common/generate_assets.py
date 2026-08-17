from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


INK = "#17324D"
COPPER = "#E07A34"
LIGHT = "#F3F7FA"


def draw_icon(size: int) -> Image.Image:
    scale = size / 256
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    margin = round(14 * scale)
    radius = round(42 * scale)
    draw.rounded_rectangle(
        (margin, margin, size - margin, size - margin),
        radius=radius,
        fill=INK,
    )

    width = max(2, round(18 * scale))
    draw.line(
        [
            (round(48 * scale), round(82 * scale)),
            (round(96 * scale), round(82 * scale)),
            (round(128 * scale), round(128 * scale)),
            (round(160 * scale), round(174 * scale)),
            (round(208 * scale), round(174 * scale)),
        ],
        fill=COPPER,
        width=width,
        joint="curve",
    )
    draw.line(
        [
            (round(48 * scale), round(174 * scale)),
            (round(96 * scale), round(174 * scale)),
            (round(128 * scale), round(128 * scale)),
            (round(160 * scale), round(82 * scale)),
            (round(208 * scale), round(82 * scale)),
        ],
        fill=LIGHT,
        width=width,
        joint="curve",
    )

    terminal_radius = max(2, round(16 * scale))
    for x, y, color in (
        (48, 82, COPPER),
        (208, 174, COPPER),
        (48, 174, LIGHT),
        (208, 82, LIGHT),
    ):
        cx, cy = round(x * scale), round(y * scale)
        draw.ellipse(
            (
                cx - terminal_radius,
                cy - terminal_radius,
                cx + terminal_radius,
                cy + terminal_radius,
            ),
            fill=color,
            outline=INK,
            width=max(1, round(4 * scale)),
        )

    center_radius = max(2, round(19 * scale))
    center = round(128 * scale)
    draw.ellipse(
        (
            center - center_radius,
            center - center_radius,
            center + center_radius,
            center + center_radius,
        ),
        fill="#FFFFFF",
        outline=COPPER,
        width=max(1, round(7 * scale)),
    )
    return image


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate WireWizardGUI package icons")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    images = [draw_icon(size) for size in (16, 24, 32, 48, 64, 128, 256)]
    images[-1].save(args.output / "wirewizard.png", format="PNG")
    images[-1].save(
        args.output / "wirewizard.ico",
        format="ICO",
        append_images=images[:-1],
        sizes=[image.size for image in images],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
