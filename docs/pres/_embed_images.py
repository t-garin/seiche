"""Inline local images as compressed WebP data URIs in an HTML file."""

import base64
import io
import pathlib
import re
import sys

from PIL import Image


def main(html_path: str) -> None:
    """Replace local ``<img src>`` references with embedded WebP data URIs."""
    path = pathlib.Path(html_path)
    html = path.read_text()

    def embed(match: re.Match) -> str:
        prefix, src, suffix = match.groups()
        if src.startswith(("data:", "http", "#")):
            return match.group(0)
        image = Image.open(path.parent / src)
        if image.mode in ("RGBA", "LA", "P"):
            image = image.convert("RGBA")
        else:
            image = image.convert("RGB")
        buffer = io.BytesIO()
        image.save(buffer, "WEBP", quality=80)
        data = base64.b64encode(buffer.getvalue()).decode()
        return f"{prefix}data:image/webp;base64,{data}{suffix}"

    path.write_text(re.sub(r'(<img\b[^>]*?src=")([^"]+)(")', embed, html))


if __name__ == "__main__":
    main(sys.argv[1])
