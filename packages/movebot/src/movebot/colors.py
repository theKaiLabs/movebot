"""LED colours by name, hex code or (red, green, blue)."""

from __future__ import annotations

from typing import Any

COLORS: dict[str, tuple[int, int, int]] = {
    "red": (255, 0, 0),
    "orange": (255, 110, 0),
    "yellow": (255, 210, 0),
    "green": (0, 220, 0),
    "cyan": (0, 220, 220),
    "blue": (0, 60, 255),
    "purple": (150, 0, 255),
    "magenta": (255, 0, 200),
    "pink": (255, 90, 160),
    "white": (255, 255, 255),
    "warm_white": (255, 190, 120),
}


def to_rgb(color: Any) -> tuple[int, int, int]:
    """``"red"``, ``"#ff8800"``, ``(255, 136, 0)`` -> ``(255, 136, 0)``."""
    if isinstance(color, str):
        name = color.strip().lower().replace(" ", "_").replace("-", "_")
        if name in COLORS:
            return COLORS[name]
        code = name.lstrip("#")
        if len(code) == 6:
            try:
                return int(code[0:2], 16), int(code[2:4], 16), int(code[4:6], 16)
            except ValueError:
                pass
        raise ValueError(
            f"unknown colour {color!r}: use a name ({', '.join(COLORS)}), "
            "a code like '#ff8800', or (red, green, blue)"
        )
    try:
        r, g, b = (round(float(c)) for c in color)
    except (TypeError, ValueError):
        raise ValueError(
            f"a colour is a name, '#rrggbb' or (red, green, blue), not {color!r}"
        ) from None
    if not all(0 <= c <= 255 for c in (r, g, b)):
        raise ValueError(f"colour values go from 0 to 255, not {color!r}")
    return r, g, b
