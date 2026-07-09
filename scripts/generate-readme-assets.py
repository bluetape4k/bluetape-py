#!/usr/bin/env python3
"""Generate source-backed README SVG assets for bluetape-py."""

from __future__ import annotations

from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets"
DIAGRAMS = ROOT / "docs" / "images" / "readme-diagrams"

FONT_TITLE = "Architects Daughter, ui-rounded, system-ui, sans-serif"
FONT_TEXT = "Comic Mono, ui-monospace, SFMono-Regular, Menlo, monospace"


def svg_text(
    x: int | float,
    y: int | float,
    text: str,
    *,
    size: int = 24,
    fill: str = "#172033",
    weight: str = "400",
    anchor: str = "middle",
    family: str = FONT_TEXT,
) -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" '
        f'dominant-baseline="middle">{escape(text)}</text>'
    )


def multiline(
    x: int | float,
    y: int | float,
    lines: list[str],
    *,
    size: int = 22,
    fill: str = "#172033",
    weight: str = "400",
    anchor: str = "middle",
    family: str = FONT_TEXT,
    line_height: int = 28,
) -> str:
    start = y - ((len(lines) - 1) * line_height / 2)
    return "\n".join(
        svg_text(
            x,
            start + i * line_height,
            line,
            size=size,
            fill=fill,
            weight=weight,
            anchor=anchor,
            family=family,
        )
        for i, line in enumerate(lines)
    )


def rect(
    x: int | float,
    y: int | float,
    w: int | float,
    h: int | float,
    *,
    fill: str,
    stroke: str = "#D9E2EF",
    rx: int = 18,
    sw: float = 2,
) -> str:
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
    )


def line(
    x1: int | float,
    y1: int | float,
    x2: int | float,
    y2: int | float,
    *,
    stroke: str = "#57708F",
    width: float = 3,
    marker: str = "url(#arrow)",
    dash: str | None = None,
) -> str:
    dashed = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" '
        f'stroke-width="{width}" stroke-linecap="round"{dashed} marker-end="{marker}"/>'
    )


def card(
    x: int,
    y: int,
    w: int,
    h: int,
    title: str,
    subtitle: str,
    *,
    fill: str,
    stroke: str,
) -> str:
    return "\n".join(
        [
            rect(x, y, w, h, fill=fill, stroke=stroke, rx=16),
            svg_text(
                x + w / 2,
                y + h * 0.34,
                title,
                size=21,
                weight="700",
                family=FONT_TITLE,
            ),
            multiline(
                x + w / 2,
                y + h * 0.72,
                subtitle.split(" | "),
                size=13,
                fill="#42526A",
                line_height=20,
            ),
        ]
    )


def defs() -> str:
    return """
  <defs>
    <linearGradient id="hero-bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#F6FAFF"/>
      <stop offset="48%" stop-color="#EDF7F5"/>
      <stop offset="100%" stop-color="#FFF7ED"/>
    </linearGradient>
    <filter id="soft-shadow" x="-12%" y="-12%" width="124%" height="130%">
      <feDropShadow dx="0" dy="10" stdDeviation="12" flood-color="#60728A" flood-opacity="0.14"/>
    </filter>
    <marker id="arrow" markerWidth="14" markerHeight="14" refX="12" refY="7"
      orient="auto" markerUnits="userSpaceOnUse">
      <path d="M 2 2 L 12 7 L 2 12 Z" fill="#57708F"/>
    </marker>
    <marker id="arrow-soft" markerWidth="10" markerHeight="10" refX="8" refY="5"
      orient="auto" markerUnits="userSpaceOnUse">
      <path d="M 2 2 L 8 5 L 2 8 Z" fill="#8A9BB0"/>
    </marker>
  </defs>
"""


def hero_svg() -> str:
    modules = [
        ("core", "stdlib-only | validation"),
        ("logging", "logging | contextvars"),
        ("testing", "pytest | internal-first"),
    ]
    module_cards = []
    for i, (title, subtitle) in enumerate(modules):
        module_cards.append(
            card(
                980,
                222 + i * 136,
                420,
                104,
                f"bluetape-{title}",
                subtitle,
                fill=["#FFFFFF", "#F9FEFC", "#FFFDF7"][i],
                stroke=["#9BC4FF", "#8EDCC7", "#F2C879"][i],
            )
        )
    intro_lines = [
        "thin default install",
        "multiple PyPI distributions",
        "one bluetape.* namespace",
        "Python 3.13+ only",
    ]
    bg = rect(0, 0, 1600, 900, fill="url(#hero-bg)", stroke="#D9E2EF", rx=0, sw=0)
    panel = rect(86, 82, 1428, 736, fill="#FFFFFF", stroke="#DCE6F2", rx=36)
    title = svg_text(
        150,
        166,
        "bluetape-py",
        size=62,
        fill="#172033",
        weight="700",
        anchor="start",
        family=FONT_TITLE,
    )
    subtitle = svg_text(
        152,
        230,
        "Python-native backend foundation",
        size=25,
        fill="#42526A",
        anchor="start",
    )
    bullets = multiline(
        154,
        338,
        intro_lines,
        size=26,
        fill="#172033",
        weight="700",
        anchor="start",
        family=FONT_TITLE,
        line_height=46,
    )
    install_box = rect(150, 526, 532, 116, fill="#F7FAFE", stroke="#B8C7DC", rx=24)
    install_title = svg_text(
        182,
        568,
        "pip install bluetape",
        size=28,
        fill="#172033",
        weight="700",
        anchor="start",
    )
    install_note = svg_text(
        182,
        612,
        "installs bluetape-core only",
        size=20,
        fill="#58677D",
        anchor="start",
    )
    extras_title = svg_text(
        1110,
        704,
        "extras open heavier capabilities explicitly",
        size=22,
        fill="#42526A",
        family=FONT_TITLE,
    )
    extras_note = svg_text(
        1110,
        746,
        "bluetape[logging] / bluetape[testing] / future adapters",
        size=18,
        fill="#58677D",
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900"
  viewBox="0 0 1600 900">
{defs()}
  {bg}
  <g filter="url(#soft-shadow)">
    {panel}
  </g>
  {title}
  {subtitle}
  {bullets}
  {install_box}
  {install_title}
  {install_note}
  {line(720, 584, 938, 584, stroke="#57708F", width=4)}
  <g>
    {"".join(module_cards)}
  </g>
  {extras_title}
  {extras_note}
</svg>
"""


def architecture_svg() -> str:
    bg = rect(0, 0, 1440, 840, fill="#F8FAFC", stroke="#D9E2EF", rx=0, sw=0)
    title = svg_text(
        720,
        64,
        "bluetape-py workspace overview",
        size=40,
        fill="#172033",
        weight="700",
        family=FONT_TITLE,
    )
    subtitle = svg_text(
        720,
        102,
        "single repository / uv workspace / focused PyPI distributions",
        size=18,
        fill="#58677D",
    )
    meta_panel = rect(72, 150, 1296, 134, fill="#FFFFFF", stroke="#CBD7E6", rx=26)
    meta_title = svg_text(720, 190, "bluetape", size=30, weight="700", family=FONT_TITLE)
    meta_note = svg_text(
        720,
        232,
        "thin meta distribution: default dependency is bluetape-core only",
        size=19,
        fill="#42526A",
    )
    core_card = card(
        492,
        336,
        456,
        124,
        "bluetape-core",
        "stdlib-only | validation foundation",
        fill="#FFFFFF",
        stroke="#9BC4FF",
    )
    logging_card = card(
        100,
        520,
        360,
        146,
        "bluetape-logging",
        "stdlib logging | contextvars | redaction",
        fill="#F9FEFC",
        stroke="#8EDCC7",
    )
    testing_card = card(
        540,
        520,
        360,
        146,
        "bluetape-testing",
        "pytest helpers | internal-first | async waits",
        fill="#FFFDF7",
        stroke="#F2C879",
    )
    future_card = card(
        980,
        520,
        360,
        146,
        "future adapters",
        "serde | cache | redis | testcontainers",
        fill="#F7FAFE",
        stroke="#B8C7DC",
    )
    footer = rect(116, 706, 1208, 76, fill="#FFFFFF", stroke="#D5DFEC", rx=18)
    footer_line1 = svg_text(
        720,
        734,
        "0.1.0 track: issues #1-#5 keep core, logging, testing, docs, "
        "and release preflight visible",
        size=18,
        fill="#42526A",
    )
    footer_line2 = svg_text(
        720,
        762,
        "Rule: Python-native APIs first; no mechanical Kotlin, Go, or Rust porting",
        size=18,
        fill="#42526A",
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="840"
  viewBox="0 0 1440 840">
{defs()}
  {bg}
  {title}
  {subtitle}

  {meta_panel}
  {meta_title}
  {meta_note}

  {line(720, 284, 720, 336, stroke="#57708F", width=4)}
  {core_card}

  {line(600, 460, 280, 520, stroke="#8A9BB0", width=3, marker="url(#arrow-soft)")}
  {line(720, 460, 720, 520, stroke="#8A9BB0", width=3, marker="url(#arrow-soft)")}
  {line(840, 460, 1160, 520, stroke="#8A9BB0", width=3, marker="url(#arrow-soft)")}

  {logging_card}
  {testing_card}
  {future_card}

  {footer}
  {footer_line1}
  {footer_line2}
</svg>
"""


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    DIAGRAMS.mkdir(parents=True, exist_ok=True)
    (ASSETS / "bluetape-py-hero.svg").write_text(hero_svg(), encoding="utf-8")
    (DIAGRAMS / "bluetape-py-workspace-overview.svg").write_text(
        architecture_svg(),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
