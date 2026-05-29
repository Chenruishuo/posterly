"""Canvas (page-size) parsing utilities, shared by all CLIs.

Two input sources for canvas dimensions:
  1. The ``@page { size: W H }`` declaration inside the poster HTML's
     ``<style>`` blocks. This is the canonical source — every CLI parses
     it first so layout decisions stay tied to what Chromium actually
     renders.
  2. The ``--canvas`` CLI argument as an override. Accepts:
       - ``60x36in``, ``914x1194mm`` (numeric W x H + unit)
       - ``A0 portrait``, ``A1 landscape`` (ISO 216 named sizes)

Returns inches everywhere; callers convert to viewport px via
``viewport_for(canvas_in)`` at 96 ppi (Chromium's print pixel basis).
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


# Conversion factors → inches.
UNIT_TO_IN: dict[str, float] = {
    "in": 1.0,
    "mm": 1.0 / 25.4,
    "cm": 1.0 / 2.54,
    "pt": 1.0 / 72.0,
}

# ISO 216 paper sizes (portrait W x H, in mm).
NAMED_SIZES_MM: dict[str, tuple[float, float]] = {
    "A0": (841.0, 1189.0),
    "A1": (594.0, 841.0),
    "A2": (420.0, 594.0),
    "A3": (297.0, 420.0),
    "A4": (210.0, 297.0),
}


def _extract_style_css(html_text: str) -> str:
    """Concatenate the contents of all ``<style>…</style>`` blocks with
    CSS comments stripped. The only place to look for ``@page`` — never
    raw HTML body, never ``<script>``.
    """
    blocks = re.findall(
        r"<style[^>]*>(.*?)</style>",
        html_text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    css = "\n".join(blocks)
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    return css


def read_canvas_from_html(html_path: Path) -> tuple[float, float] | None:
    """Parse ``@page { size: ... }`` from ``<style>`` blocks.

    Supports both numeric and named-size forms:

      - ``@page { size: 60in 36in; }`` (numeric, `in`/`mm`/`cm`/`pt`)
      - ``@page { size: A0 portrait; }`` / ``A1 landscape`` (CSS named
        page sizes — same set as ``parse_canvas_arg``)

    Numeric dimensions may mix units (``24in 914mm``). Named pages
    (``@page poster { size: ... }``) are recognised too. Returns
    ``(width_in, height_in)`` or ``None`` on parse failure — callers
    must either require ``--canvas`` or exit non-zero. We refuse to
    silently fall back to a hardcoded default.
    """
    txt = html_path.read_text(encoding="utf-8", errors="ignore")
    css = _extract_style_css(txt)

    # Numeric form first — most posters use it explicitly.
    m_num = re.search(
        r"@page(?:\s+[A-Za-z_-][\w:-]*)?\s*\{[^}]*size\s*:\s*"
        r"([\d.]+)\s*(in|mm|cm|pt)\s+"
        r"([\d.]+)\s*(in|mm|cm|pt)",
        css,
        re.IGNORECASE,
    )
    if m_num:
        w = float(m_num.group(1)) * UNIT_TO_IN[m_num.group(2).lower()]
        h = float(m_num.group(3)) * UNIT_TO_IN[m_num.group(4).lower()]
        return w, h

    # Named-size form (CSS Paged Media): `size: <name> [portrait|landscape]?`.
    m_name = re.search(
        r"@page(?:\s+[A-Za-z_-][\w:-]*)?\s*\{[^}]*size\s*:\s*"
        r"(A[0-4])(?:\s+(portrait|landscape))?\s*[;}]",
        css,
        re.IGNORECASE,
    )
    if m_name:
        name = m_name.group(1).upper()
        orient = (m_name.group(2) or "portrait").lower()
        w_mm, h_mm = NAMED_SIZES_MM[name]
        if orient == "landscape":
            w_mm, h_mm = h_mm, w_mm
        return w_mm / 25.4, h_mm / 25.4

    return None


def parse_canvas_arg(s: str) -> tuple[float, float]:
    """Argparse-friendly parser for ``--canvas`` values.

    Accepts:
      - ``60x36in``, ``914x1194mm``, ``60x36cm`` (one unit at end)
      - ``A0 portrait``, ``A0 landscape``, ``A1 portrait``, …
    Returns ``(width_in, height_in)``.

    Raises ``argparse.ArgumentTypeError`` so argparse formats the error
    cleanly without a stack trace.
    """
    s = s.strip()
    # Form 1: <W>x<H><unit>
    m = re.fullmatch(
        r"([\d.]+)\s*[x×]\s*([\d.]+)\s*(in|mm|cm|pt)",
        s,
        re.IGNORECASE,
    )
    if m:
        unit = m.group(3).lower()
        w = float(m.group(1)) * UNIT_TO_IN[unit]
        h = float(m.group(2)) * UNIT_TO_IN[unit]
        return w, h
    # Form 2: <NamedSize> [portrait|landscape]
    m = re.fullmatch(
        r"(A[0-4])(?:\s+(portrait|landscape))?",
        s,
        re.IGNORECASE,
    )
    if m:
        name = m.group(1).upper()
        orient = (m.group(2) or "portrait").lower()
        w_mm, h_mm = NAMED_SIZES_MM[name]
        if orient == "landscape":
            w_mm, h_mm = h_mm, w_mm
        return w_mm / 25.4, h_mm / 25.4
    raise argparse.ArgumentTypeError(
        f"--canvas expects '<W>x<H><unit>' (e.g. '60x36in') or "
        f"'<NamedSize> [portrait|landscape]' (e.g. 'A0 portrait'); "
        f"got {s!r}. Named sizes: {', '.join(sorted(NAMED_SIZES_MM))}."
    )


def viewport_for(canvas_in: tuple[float, float]) -> tuple[int, int]:
    """Convert (W_in, H_in) to (W_px, H_px) at 96 ppi.

    Playwright's print-emulation uses CSS pixels at 96 ppi, so the
    viewport must match that basis or measurement units shift.
    """
    w_in, h_in = canvas_in
    return (int(round(w_in * 96)), int(round(h_in * 96)))


def resolve_canvas(
    html_path: Path,
    canvas_override: tuple[float, float] | None,
    label: str,
) -> tuple[tuple[float, float], tuple[int, int]] | None:
    """Resolve canvas from CLI override (preferred) or HTML's ``@page``.

    Prints a one-liner to stdout describing which source was used.
    Returns ``(canvas_in, viewport_px)`` on success, ``None`` on failure
    (caller exits 2 after this). ``label`` is the CLI's logger prefix
    (e.g. ``[measure]``).
    """
    if canvas_override is not None:
        canvas = canvas_override
        print(f"{label} canvas (--canvas override) = "
              f"{canvas[0]:.2f}in × {canvas[1]:.2f}in")
    else:
        parsed = read_canvas_from_html(html_path)
        if parsed is None:
            return None
        canvas = parsed
        print(f"{label} canvas = {canvas[0]:.2f}in × {canvas[1]:.2f}in")
    viewport = viewport_for(canvas)
    print(f"{label} viewport = {viewport[0]} × {viewport[1]} px")
    return canvas, viewport
