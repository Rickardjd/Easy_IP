#!/usr/bin/env python3
"""
Generate the Easy IP application icon from Easy_IP.png in the project root.
Requires: pip install pillow
Output:   assets/icon.ico  (16, 32, 48, 256 px multi-size)
"""

import os
from PIL import Image


def create_icon(out_path: str | None = None) -> str:
    """Convert Easy_IP.png to a multi-resolution .ico and write it to *out_path*."""
    if out_path is None:
        out_path = os.path.join(os.path.dirname(__file__), "icon.ico")

    # Resolve the PNG path relative to the project root (one level up from assets/)
    script_dir  = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    png_path = os.path.join(project_root, "Easy_IP.png")

    if not os.path.isfile(png_path):
        raise FileNotFoundError(
            f"Source icon not found: {png_path}\n"
            "Place Easy_IP.png in the project root folder and retry."
        )

    print(f"Loading source icon from: {png_path}")
    src = Image.open(png_path).convert("RGBA")

    sizes  = [16, 32, 48, 256]
    frames = [src.resize((s, s), Image.LANCZOS) for s in sizes]

    frames[0].save(
        out_path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=frames[1:],
    )
    print(f"Icon written -> {out_path}")
    return out_path


if __name__ == "__main__":
    create_icon()
