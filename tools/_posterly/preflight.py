"""Static HTML lint — runs before any rendering.

Catches the classes of errors that would otherwise burn a render cycle:

- LaTeX residue (``\\ref{`` / ``\\cite{`` / ``\\textbf{`` / lone ``\\ ``).
- Raw ``<`` inside ``$…$`` / ``$$…$$`` / ``\\(…\\)`` / ``\\[…\\]`` —
  MathJax may HTML-parse it as a tag start depending on its loader mode.
- Local ``src="..."`` images that don't exist on disk.
- Missing or unknown ``data-measure-role`` values.
- Measure-role nesting: each role is checked against the templates'
  parent contract (e.g. ``card`` must sit inside a ``column``/``hero``,
  not directly under ``body``). A misplaced ``</div>`` that closes the
  body grid early would otherwise pass preflight + measure -- the body
  ``1fr`` row absorbs the lost children, and the gap-to-strip number
  goes off-canvas without surfacing the actual structural cause.

The line numbers reported by preflight refer to **the original HTML file**.
Earlier versions stripped ``<style>`` / ``<script>`` / ``<!-- … -->``
blocks with ``re.sub(... , "")``, which collapsed newlines and shifted
every subsequent line number by N. We now replace each stripped block
with the SAME NUMBER OF NEWLINES, so character offsets after the strip
still map to the same line in the original file.
"""
from __future__ import annotations

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit


# Roles understood by ``measure`` / ``polish``. Anything outside this
# set in a ``data-measure-role`` attribute is almost certainly a typo
# and would silently be ignored by the geometry pass.
KNOWN_ROLES: set[str] = {
    "poster", "header", "banner", "body", "band",
    "column", "card", "hero", "footer-strip", "footer",
}


# Required parent role(s) for each measure role, derived from the three
# shipped templates (landscape_4col / landscape_hero / portrait_2col).
# Multiple entries mean "any of these is OK". Roles whose parent must be
# the document root (``poster``) are listed too. Empty tuple => no
# constraint (e.g. ``poster`` itself, which is the root).
#
# Background: a misplaced ``</div>`` was the precipitating bug for this
# gate. It closed ``.poster`` (the grid container) before its
# ``footer-strip`` and ``footer`` children appeared in source order, so
# those nodes ended up outside the grid. The browser tolerated it; the
# CSS ``grid-template-rows: auto auto 1fr auto auto`` collapsed two
# rows to 0 px without complaint; measure reported the strip top off-
# canvas. This rule turns that silent failure into a preflight error
# pointing at the role whose parent went wrong.
ROLE_PARENTS: dict[str, tuple[str, ...]] = {
    "header":       ("poster",),
    "banner":       ("poster",),
    # ``band`` is the full-width CONTENT band of the portrait skeletons
    # (DESIGN-AXES.md, Axis 1 portrait translations): like ``banner`` its
    # bottom never feeds the column-alignment spread, but unlike banner
    # its content IS scanned by the clip / broken-image / letterbox gates.
    "band":         ("poster",),
    "body":         ("poster",),
    # ``body`` is allowed for footer-strip/footer for the same reason
    # ``poster`` is allowed for column/hero below: a hand-rolled layout
    # may nest the strip inside the body container, and measure reads
    # the strip's rendered position regardless of where it sits. The
    # precipitating bug (strip escaping to the *document root* after a
    # stray ``</div>``) is still caught -- root has no role.
    "footer-strip": ("poster", "body"),
    "footer":       ("poster", "body"),
    # ``poster`` is allowed for column/hero because ``body`` was never
    # required by any gate -- a poster hanging its columns directly off
    # the root is valid today and measures fine.
    "column":       ("body", "poster"),
    "hero":         ("body", "poster"),
    "card":         ("column", "hero"),
}


# (regex, human description) pairs for LaTeX residue. The patterns are
# scanned over the body with style/script/comments stripped (newline-
# preserved), so each match's character offset still maps to the right
# line in the original file.
LATEX_PATTERNS: list[tuple[str, str]] = [
    (r"\\ref\{",        r"\\ref{...} residue"),
    (r"\\cite\{",       r"\\cite{...} residue"),
    (r"\\textbf\{",     r"\\textbf{...} residue (use <b> or **bold**)"),
    (r"\\textit\{",     r"\\textit{...} residue (use <i> or *italic*)"),
    (r"\\emph\{",       r"\\emph{...} residue"),
    (r"\\section\{",    r"\\section{...} residue"),
    (r"\\label\{",      r"\\label{...} residue"),
    (r"\\begin\{",      r"\\begin{...} residue (use HTML structures)"),
    (r"\\end\{",        r"\\end{...} residue"),
    (r"(?<![\\a-zA-Z])\\\s",
        r"backslash-space '\\ ' (will render literally)"),
]


from .textutil import ascii_safe


def _eprint(*args: Any, **kw: Any) -> None:
    print(*args, file=sys.stderr, **kw)


def _newline_preserving_sub(pattern: str, html: str, *,
                            flags: int = 0) -> str:
    """Replace each match with ``\\n`` * <newline-count-in-match>.

    This preserves line numbers across ``<style>`` / ``<script>`` /
    ``<!-- … -->`` blocks so a regex match's character offset in the
    stripped output still maps to the same line in the original file.
    """
    def keep_newlines(m: re.Match) -> str:
        return "\n" * m.group(0).count("\n")
    return re.sub(pattern, keep_newlines, html, flags=flags)


def strip_for_lint(html: str) -> str:
    """Remove ``<style>``, ``<script>``, and HTML comments while
    preserving newline counts. The output is what every preflight rule
    scans against.

    ONE document-order pass over all three so a construct nested inside
    another is consumed as a single unit by whichever delimiter opens
    FIRST. Stripping them in separate passes was a bug: a comment that
    contained ``<script>`` (e.g. ``<!-- ... change the <script> src -->``)
    had its closing ``-->`` eaten by the script pass, after which the
    comment pass ran past it and deleted real body markup downstream --
    the root ``<div data-measure-role="poster">`` went missing, so
    preflight false-failed "missing poster". The combined alternation
    also handles the reverse (a ``<style>``/``<script>`` body containing
    ``-->`` or ``<!--``): the tag opens first, so its whole body is taken
    before the comment rule can match inside it.
    """
    return _newline_preserving_sub(
        r"<!--.*?-->"
        r"|<style[^>]*>.*?</style>"
        r"|<script[^>]*>.*?</script>",
        html, flags=re.DOTALL | re.IGNORECASE,
    )


def find_math_segments(text: str) -> list[tuple[int, int, str]]:
    """Find inline + display math segments. Returns ``[(start, end, body)]``.

    Supports the four delimiter pairs every Claude-poster template
    configures MathJax for:

      - ``$$ … $$`` (display)
      - ``$ … $`` (inline; excludes already-covered ``$$`` regions)
      - ``\\[ … \\]`` (display)
      - ``\\( … \\)`` (inline)
    """
    out: list[tuple[int, int, str]] = []

    def add(s: int, e: int, body: str) -> None:
        out.append((s, e, body))

    # $$...$$
    for m in re.finditer(r"\$\$(.+?)\$\$", text, re.DOTALL):
        add(m.start(), m.end(), m.group(1))
    # \[...\]
    for m in re.finditer(r"\\\[(.+?)\\\]", text, re.DOTALL):
        add(m.start(), m.end(), m.group(1))

    covered = [(s, e) for s, e, _ in out]

    # $...$ — single-line only, not already inside a $$...$$
    for m in re.finditer(r"(?<!\$)\$(?!\$)([^$\n]+?)\$(?!\$)", text):
        s, e = m.start(), m.end()
        if any(cs <= s < ce or cs < e <= ce for cs, ce in covered):
            continue
        add(s, e, m.group(1))
    # \(...\) — single-line only, not already inside a \[...\]
    for m in re.finditer(r"\\\(([^\n]+?)\\\)", text):
        s, e = m.start(), m.end()
        if any(cs <= s < ce or cs < e <= ce for cs, ce in covered):
            continue
        add(s, e, m.group(1))

    return out


def _delim_label(body: str, segment: str) -> str:
    """Try to label a math segment by its delimiter style in error
    output. ``segment`` is the raw matched text; we look at its first
    char(s)."""
    if segment.startswith("$$") and segment.endswith("$$"):
        return "$$...$$"
    if segment.startswith("$") and segment.endswith("$"):
        return "$...$"
    if segment.startswith("\\["):
        return "\\[...\\]"
    if segment.startswith("\\("):
        return "\\(...\\)"
    return "math"


# Tags that the HTML spec lists as void / self-closing -- they have no
# end tag and must never push onto the parser stack. Lower-cased; the
# parser hands us tag names already lowered. Includes the long-tail
# rare ones (``<keygen>``, ``<menuitem>``) the spec retains for parsers
# even if browsers no longer render them, so a poster importing legacy
# markup doesn't trip a false unbalance error.
_VOID_TAGS: frozenset[str] = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "keygen", "link", "menuitem", "meta", "param", "source",
    "track", "wbr",
})


class _RoleNestingChecker(HTMLParser):
    """Walk the HTML and record each ``data-measure-role`` element's
    nearest ancestor that itself carries a role.

    Why a stack-based scanner and not a regex pass: the bug we want to
    catch is a misplaced ``</div>`` that closes ``.poster`` early, so a
    ``footer-strip`` later in source order ends up *outside* the
    poster. A regex over ``data-measure-role`` would still see the
    strip and call it good. The browser tolerates the unbalanced markup
    silently; only an actual nesting model surfaces the lost ancestry.

    The parser intentionally does NOT bail on every minor unbalance --
    HTMLParser's recovery is generous and matches the browser's --
    because we only care about role-bearing ancestry. We do, however,
    catch the *gross* unbalance case: a ``</tag>`` that finds no
    matching opener on the stack. That is almost always the symptom of
    the same misplaced-``</div>`` bug.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        # Stack entries: (tag, role_or_None, line_number).
        self.stack: list[tuple[str, str | None, int]] = []
        # One entry per role-bearing element seen, in source order:
        # (role, parent_role_or_None, line, tag).
        self.roles: list[tuple[str, str | None, int, str]] = []
        # Lines where ``</tag>`` had no matching opener.
        self.stray_close_lines: list[tuple[str, int]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]
                        ) -> None:
        role: str | None = None
        for k, v in attrs:
            if k == "data-measure-role" and v is not None:
                role = v.strip()
                break
        line = self.getpos()[0]
        if role is not None:
            # Parent role = the nearest ancestor on the stack that carries
            # a role. None means the element is at document root or only
            # nested inside non-role wrappers.
            parent_role: str | None = None
            for _t, r, _ln in reversed(self.stack):
                if r is not None:
                    parent_role = r
                    break
            self.roles.append((role, parent_role, line, tag))
        if tag.lower() not in _VOID_TAGS:
            self.stack.append((tag, role, line))

    def handle_startendtag(self, tag: str,
                           attrs: list[tuple[str, str | None]]) -> None:
        # ``<foo />`` self-closing form. Record any role but DON'T push.
        role: str | None = None
        for k, v in attrs:
            if k == "data-measure-role" and v is not None:
                role = v.strip()
                break
        if role is not None:
            line = self.getpos()[0]
            parent_role: str | None = None
            for _t, r, _ln in reversed(self.stack):
                if r is not None:
                    parent_role = r
                    break
            self.roles.append((role, parent_role, line, tag))

    def handle_endtag(self, tag: str) -> None:
        # Pop until we find the matching opener. If none is found, the
        # closer is stray -- record it and leave the stack alone (the
        # browser would do the same, just silently).
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                # Pop everything from i onward; entries above are
                # implicitly unclosed (HTMLParser does not auto-close)
                # but treating them as closed here matches browser
                # recovery and avoids a cascade of false stray-close
                # reports for the rest of the document.
                del self.stack[i:]
                return
        self.stray_close_lines.append((tag, self.getpos()[0]))


class _FigureCaptionChecker(HTMLParser):
    """Track every ``.figure`` block (class TOKEN ``figure``) and whether
    it contains a ``.caption`` descendant with non-empty text.

    posterly's figure-card contract is ``.figure > img + .caption`` -- a
    figure that ships without its one-line caption reads as an unlabeled
    image on the wall. Keyed on the CLASS token, not the ``<figure>``
    tag: the only ``<figure>`` element in the templates is the framework
    banner's ``banner-figure``, which is captionless BY DESIGN (its
    banner text is the explanation), and the hero stage's caption is
    optional -- neither carries the ``figure`` class token, so neither
    is scanned. Stack discipline mirrors :class:`_RoleNestingChecker`.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        # Stack entries: (tag, kind, fig_record_or_None); kind is
        # "figure", "caption", or None.
        self.stack: list[tuple[str, str | None, dict | None]] = []
        self.figs: list[dict] = []

    @staticmethod
    def _classes(attrs: list[tuple[str, str | None]]) -> list[str]:
        for k, v in attrs:
            if k == "class" and v:
                return v.split()
        return []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]
                        ) -> None:
        if tag.lower() in _VOID_TAGS:
            return
        classes = self._classes(attrs)
        kind: str | None = None
        rec: dict | None = None
        if "figure" in classes:
            kind = "figure"
            rec = {"line": self.getpos()[0], "has_caption": False}
            self.figs.append(rec)
        elif "caption" in classes:
            kind = "caption"
        self.stack.append((tag, kind, rec))

    def handle_data(self, data: str) -> None:
        if not data.strip():
            return
        if not any(k == "caption" for _t, k, _r in self.stack):
            return
        # Credit the nearest enclosing .figure (a caption outside any
        # figure block is someone else's caption -- ignore it).
        for _t, k, r in reversed(self.stack):
            if k == "figure" and r is not None:
                r["has_caption"] = True
                return

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                return


def figures_missing_caption(html: str) -> list[int]:
    """Line numbers (1-based) of ``.figure`` blocks that contain no
    ``.caption`` descendant with non-empty text. Pure function so the
    rule is unit-testable without the filesystem.
    """
    parser = _FigureCaptionChecker()
    parser.feed(html)
    parser.close()
    return [f["line"] for f in parser.figs if not f["has_caption"]]


def check_role_nesting(html: str
                       ) -> tuple[list[tuple[str, str | None, int, str]],
                                  list[tuple[str, int]]]:
    """Return ``(roles, stray_closes)``.

    ``roles`` is one entry per role-bearing element in source order:
    ``(role, parent_role_or_None, line, tag)``. ``stray_closes`` lists
    every ``</tag>`` that had no opener on the stack at close time --
    almost always the proximate cause when ``measure`` reports the
    footer-strip rendered off-canvas. Pure function so the rule can be
    unit-tested without touching the filesystem or a browser.
    """
    parser = _RoleNestingChecker()
    parser.feed(html)
    parser.close()
    return parser.roles, parser.stray_close_lines


# SVG contexts whose children do not render on their own: definition blocks
# (defs / symbol / clipPath / mask / marker / pattern / filter), gradient
# bodies (their children are stops), and metadata containers (desc / title /
# metadata). A shape or <use> inside any of these paints nothing directly.
_SVG_DEFS_CTX: frozenset[str] = frozenset({
    "defs", "symbol", "clippath", "mask", "marker", "pattern", "filter",
    "lineargradient", "radialgradient", "metadata", "desc", "title",
})

_NUM_PREFIX = re.compile(r"^[+-]?(?:\d+\.?\d*|\.\d+)")
# A well-formed SVG length: number + optional unit and NOTHING else. Chromium
# treats '25banana' as invalid (renders as 0), so a numeric-prefix-only check
# would call a blank shape drawable.
_LEN_RE = re.compile(
    r"^[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?"
    r"(?:px|%|em|rem|ex|ch|pt|pc|mm|cm|in|q)?$", re.I)


def _pos_len(v: str) -> bool:
    """A positive, WELL-FORMED SVG length ('25', '25px', '30%'). Malformed
    ('25banana'), empty, zero ('0mm') and negative values all render as
    nothing in the browser and are rejected."""
    v = (v or "").strip()
    if not _LEN_RE.match(v):
        return False
    return float(_NUM_PREFIX.match(v).group(0)) > 0


def _coord_ok(v: str) -> bool:
    """A well-formed coordinate (zero / negative allowed)."""
    return bool(_LEN_RE.match((v or "").strip()))


def _classify_sym_child(tag: str, attrs: dict[str, str]) -> str | None:
    """Classify a child on the #psReg symbol's render path for the
    canonical-glyph check.

    The identity glyph is the canonical ⊕ -- one circle + two crosshair
    lines, shipped byte-identical across templates and copied verbatim by
    authors -- so the gate verifies THAT structure instead of running a
    general "some SVG might paint" heuristic (which was simultaneously too
    lenient on malformed geometry and too strict on legitimate SVG defaults).

    Returns ``'circle'`` / ``'line'`` for a well-formed instance of the two
    canonical parts (a line must be non-degenerate -- a zero-length line
    draws nothing), ``'other'`` for anything else drawable-ish (wrong shape
    types, malformed geometry, nested ``<use>`` indirection -- which can
    dangle or self-recurse), and ``None`` for non-drawing wrappers/metadata
    (``<g>``, ``<desc>``, ...) that don't affect the glyph.
    """
    if tag == "circle":
        return "circle" if _pos_len(attrs.get("r", "")) else "other"
    if tag == "line":
        coords = [(attrs.get(k, "") or "").strip()
                  for k in ("x1", "y1", "x2", "y2")]
        if not all(_coord_ok(c) for c in coords):
            return "other"
        x1, y1, x2, y2 = (float(_NUM_PREFIX.match(c).group(0))
                          for c in coords)
        return "line" if (x1, y1) != (x2, y2) else "other"
    if tag in ("path", "rect", "ellipse", "polygon", "polyline", "use",
               "text", "image"):
        return "other"
    return None


class _IdentityScanner(HTMLParser):
    """Structural scan of the identity-v1 contract, scoped to the poster root.

    A stack-based DOM walk (mirroring :class:`_RoleNestingChecker`) rather than
    whole-document regexes, because the contract is about *structure and
    scope*, not string presence. It assumes reasonably canonical HTML (void
    elements self-close, non-void ones do not; shapes are not left unclosed
    around siblings) -- the shipped templates are. Where non-canonical markup
    matters (an unclosed ``<circle>`` swallowing the sibling lines), the
    canonical-glyph walk is built to err toward FAIL, not pass.

    - **Document-wide counting, root-anchored state.** The whole HTML file
      prints, so ``data-ps-mark`` / ``<use>`` / ornament are counted across
      the entire document (outside inert ``<template>`` subtrees) -- an
      absolutely-positioned mark accidentally left OUTSIDE the poster div
      still lands on the PDF, so scoping the count to the root subtree would
      be a blind spot. The poster root (``data-measure-role="poster"``) only
      anchors the STATE: ``data-ps-identity`` is read there and nowhere else
      (a state attribute sighted anywhere ELSE is recorded so a misplaced
      state fails loudly instead of silently downgrading the poster to
      legacy). A ``data-ps-identity`` string shown as literal text in a
      ``<code>`` sample is never an attribute, so the parser ignores it for
      free.
    - **Per-mark accounting.** Each frame tracks how many live ``<use>`` it
      wraps; a mark must wrap EXACTLY one, and every live ``<use>`` must belong
      to a mark -- so neither an empty mark nor a stray unwrapped ``<use>``
      (which still paints a glyph, defeating anonymity) slips through. The
      poster root itself must never BE a mark (a descendant ``<use>`` anywhere
      would satisfy it).
    - **Live glyph, real namespace, canonical shape.** A ``<use
      href="#psReg">`` only instantiates the glyph in the SVG namespace
      (``<svg>`` enters it, ``<foreignObject>`` switches back to HTML) and
      outside a non-rendering context (:data:`_SVG_DEFS_CTX`). EVERY ``#psReg``
      reference is ALSO counted separately: defs content (a
      ``<pattern>``/``<mask>``) can still reach the canvas via
      ``fill="url(#...)"``, so ``off`` requires zero references and ``on``
      requires every reference to be a live, mark-wrapped instance. Fragment
      resolution takes the FIRST element with ``id="psReg"`` in the document
      (symbol or not -- a duplicate id shadows the sprite), and that element
      must be an SVG-namespace ``<symbol>`` whose render path (direct
      children, ``<g>`` wrapping allowed) carries the canonical ⊕: exactly
      one circle + two lines.

    Independent identity fields per stack frame (``mark_kind`` / ``sym_path``
    / ``ns`` / ``defs``) rather than a single ``role``, so one element can be
    several at once.

    Still an accidental-breakage lint, not a tamper-proof boundary: the marks
    are visible and removable by design, and forgery is out of scope.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[dict] = []
        self.state: str | None = None       # data-ps-identity on the root
        self.state_attr_anywhere = False    # data-ps-identity on ANY element
        self.has_contract = False           # any identity-v1 contract attr
        self.gen_meta = False               # <meta generator=posterly>
        self.root_seen = False
        self.root_mark = False             # data-ps-mark on the poster root
        self.shadow_template = False       # template[shadowrootmode] (DSD)
        self.corner = 0                    # document-wide counts...
        self.woven = 0
        self.corner_in_root = 0            # ...and inside the poster root
        self.woven_in_root = 0
        self.unknown_marks = 0              # data-ps-mark value not corner/woven
        self.marks_without_use = 0         # mark wrapping zero live <use>
        self.marks_multi_use = 0           # mark wrapping more than one live <use>
        self.use_total = 0                 # live <use href="#psReg"> instances
        self.uses_outside_mark = 0         # live <use> not inside any mark
        self.psreg_refs = 0                # ANY #psReg <use> ref in the doc
        self.symbol_seen = False           # any <symbol id="psReg"> exists
        self.psreg_first: str | None = None  # what the FIRST id="psReg" is:
        #                                     "symbol-svg"|"symbol-html"|"other"
        self.sym_circles = 0               # canonical parts on the render path
        self.sym_lines = 0
        self.sym_other = 0
        self.ornament = False

    @staticmethod
    def _attrs(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        # First value wins on a duplicated attribute, matching the browser HTML
        # parser (html.parser hands them left-to-right).
        out: dict[str, str] = {}
        for k, v in attrs:
            out.setdefault(k.lower(), v or "")
        return out

    def _in(self, key: str) -> bool:
        return any(f.get(key) for f in self.stack)

    def _open(self, tag: str, attrs: list[tuple[str, str | None]],
              void: bool) -> None:
        tag = tag.lower()
        a = self._attrs(attrs)
        is_void = void or tag in _VOID_TAGS

        # <template> content is inert (never rendered) -- skip its subtree.
        # EXCEPT declarative shadow DOM (template[shadowrootmode]), which DOES
        # render: record it so the poster is hard-rejected rather than blindly
        # skipped (we don't model shadow-tree id/mark scoping). <noscript>
        # content never renders in the scripting-enabled Chromium export, so
        # it is skipped too (its fallback marks would be parser-only ghosts).
        if tag in ("template", "noscript"):
            if tag == "template" and "shadowrootmode" in a:
                self.shadow_template = True
            if not is_void:
                self.stack.append({"tag": tag, "skip": True})
            return
        if self._in("skip"):
            if not is_void:
                self.stack.append({"tag": tag})
            return

        # Document-global "this is a posterly poster" signals.
        if tag == "meta" and a.get("name", "").strip().lower() == "generator" \
                and a.get("content", "").strip().lower() == "posterly":
            self.gen_meta = True
        if a.get("data-posterly-contract", "").strip().lower() == "identity-v1":
            self.has_contract = True
        # A data-ps-identity attribute sighted ANYWHERE (even off the root):
        # a misplaced state must fail loudly, not silently downgrade to legacy.
        if "data-ps-identity" in a:
            self.state_attr_anywhere = True

        frame: dict = {"tag": tag}

        # Namespace: <svg> enters the SVG namespace; the HTML integration
        # points (<foreignObject>, and SVG <desc>/<title>) switch their
        # CHILDREN back to HTML until a nested <svg>. A <use>/<symbol> in
        # HTML flow is an unknown element that renders nothing, so everything
        # below keys on the REAL namespace, not "has an <svg> ancestor".
        # (frame["ns"] is the namespace context for the element's children.)
        parent = self.stack[-1] if self.stack else None
        if tag == "svg":
            ns = "svg"
        elif tag in ("foreignobject", "desc", "title"):
            ns = "html"
        else:
            ns = parent.get("ns", "html") if parent else "html"
        frame["ns"] = ns
        in_svg = ns == "svg"

        # Poster root = the data-measure-role="poster" element. State is read
        # ONLY here; everything else is counted document-wide (the whole file
        # prints, so a mark outside this div still lands on the PDF).
        is_root = False
        if not self.root_seen and a.get("data-measure-role") == "poster":
            self.root_seen = True
            is_root = True
            frame["root"] = True
            if "data-ps-identity" in a:
                self.state = a["data-ps-identity"].strip().lower()
        in_root = is_root or self._in("root")

        # Non-rendering SVG contexts -- only meaningful in the SVG namespace
        # (an HTML <symbol> inside <foreignObject> is just an unknown
        # element, not a defs context).
        if in_svg and tag in _SVG_DEFS_CTX:
            frame["defs"] = True
        in_defs = frame.get("defs", False) or self._in("defs")

        # Fragment resolution takes the FIRST element with id="psReg" in the
        # document, symbol or not -- a duplicate id on some other element
        # shadows the sprite entirely. Record what that first element is; the
        # canonical-glyph counters then run only on the render path of a
        # first-and-valid <symbol>.
        if a.get("id") == "psReg" and self.psreg_first is None:
            if tag == "symbol":
                self.psreg_first = "symbol-svg" if in_svg else "symbol-html"
                if in_svg and not is_void:
                    frame["sym_path"] = True
            else:
                self.psreg_first = "other"
        if tag == "symbol" and a.get("id") == "psReg":
            self.symbol_seen = True
        # The render path propagates ONLY through explicit <g> wrappers: a
        # shape never legitimately parents other shapes, so an unclosed
        # <circle> that swallowed its sibling lines must NOT keep counting
        # them (the browser nests them under the circle, where they don't
        # paint), and defs/metadata/etc. subtrees stay off-path implicitly.
        if parent is not None and parent.get("sym_path") and tag == "g":
            frame["sym_path"] = True
        if parent is not None and parent.get("sym_path"):
            k = _classify_sym_child(tag, a)
            if k == "circle":
                self.sym_circles += 1
            elif k == "line":
                self.sym_lines += 1
            elif k == "other":
                self.sym_other += 1

        # <use href="#psReg"> (fragment case-sensitive; an EXISTING href wins
        # over xlink:href even when empty, per SVG2 -- Chromium agrees).
        href = (a["href"] if "href" in a else a.get("xlink:href", "")).strip()
        if tag == "use" and href == "#psReg":
            # ANY reference counts: defs content (a <pattern>/<mask>) can
            # still reach the canvas via fill="url(#...)", and "off" must
            # guarantee zero glyphs on the PDF.
            self.psreg_refs += 1
            # A LIVE use (SVG namespace, outside defs) instantiates a glyph
            # directly; attribute it to the nearest enclosing mark. A live use
            # with no mark is a stray glyph.
            if in_svg and not in_defs:
                self.use_total += 1
                for f in reversed(self.stack):
                    if "mark_kind" in f:
                        f["use_count"] = f.get("use_count", 0) + 1
                        break
                else:
                    self.uses_outside_mark += 1

        # data-ps-mark, counted document-wide AND per root-subtree. The value
        # must be the EXACT string "corner"/"woven": every downstream consumer
        # -- the woven sizing CSS, the polish probe -- uses case-sensitive
        # attribute selectors, so a "WOVEN" that a lenient gate accepted would
        # silently miss its sizing rule and blow up to column width.
        if "data-ps-mark" in a:
            if is_root:
                # The poster root must never BE the mark: any descendant <use>
                # would satisfy its containment, which is not the documented
                # corner/woven placement. Hard-rejected in the problems list.
                self.root_mark = True
            else:
                k = a["data-ps-mark"]
                if k == "corner":
                    self.corner += 1
                    if in_root:
                        self.corner_in_root += 1
                elif k == "woven":
                    self.woven += 1
                    if in_root:
                        self.woven_in_root += 1
                else:
                    self.unknown_marks += 1
                if is_void:
                    # A void / self-closed element can't wrap a <use>.
                    if k in ("corner", "woven"):
                        self.marks_without_use += 1
                elif k in ("corner", "woven"):
                    # An unknown-valued mark is NOT a mark frame: a <use>
                    # inside it counts as stray (it already hard-fails on the
                    # unknown value anyway).
                    frame["mark_kind"] = k
                    frame["use_count"] = 0

        # Live .ornament (class TOKEN), document-wide.
        if "ornament" in a.get("class", "").split():
            self.ornament = True

        if not is_void:
            self.stack.append(frame)

    def _finalize(self, frame: dict) -> None:
        if "mark_kind" not in frame:
            return
        n = frame.get("use_count", 0)
        if n == 0:
            self.marks_without_use += 1
        elif n > 1:
            self.marks_multi_use += 1

    def handle_starttag(self, tag: str,
                        attrs: list[tuple[str, str | None]]) -> None:
        self._open(tag, attrs, void=False)

    def handle_startendtag(self, tag: str,
                           attrs: list[tuple[str, str | None]]) -> None:
        self._open(tag, attrs, void=True)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]["tag"] == tag:
                for f in self.stack[i:]:
                    self._finalize(f)
                del self.stack[i:]
                return

    def close(self) -> None:
        super().close()
        # Finalize any marks left unclosed at EOF (HTMLParser won't emit their
        # end tags) so a truncated empty mark still counts.
        for f in self.stack:
            self._finalize(f)
        self.stack = []


def identity_mark_problems(html: str) -> list[str]:
    """Identity-mark (identity-v1) contract check. Pure + unit-testable.

    Reads ``data-ps-identity`` on the poster root and enforces:

      - ``on``  -> exactly one ``data-ps-mark="corner"``; at most one
        ``data-ps-mark="woven"`` (the woven mark is an authoring rule, so
        ITS absence is only a soft polish advisory, not a preflight fail --
        we only reject a duplicate here).
      - ``off`` -> ZERO corner AND zero woven. Anonymity must REMOVE every
        mark, not merely relax a gate; otherwise the gate goes green while
        the rendered PDF still carries the mark.
      - absent  -> legacy HTML ONLY when the doc carries no identity signal
        at all (no ``identity-v1`` contract, no posterly generator ``<meta>``,
        and no ``data-ps-identity`` attribute anywhere); a doc that declares
        either signal but has no state on the poster ROOT is a new poster
        missing (or misplacing) its identity and fails. Pre-identity fixtures
        with no signal are left alone.

    Plus structural integrity, independent of state: the first ``id="psReg"``
    element must be an SVG-namespace ``<symbol>`` carrying the canonical ⊕
    (exactly one circle + two lines on its render path); each ``data-ps-mark``
    must wrap exactly one live ``<use>`` of it; under ``on`` every ``#psReg``
    reference must BE such a live mark-wrapped instance; and a live
    (uncommented) legacy ``.ornament`` is rejected while identity is active
    (it is superseded by the corner-signature). Marks and references are
    counted document-wide -- the whole file prints, so "outside the poster
    div" is not outside the PDF.

    This is an accidental-breakage lint, not a tamper-proof boundary: the marks
    are visible and removable by design; forgery is out of scope. The scan is a
    :class:`_IdentityScanner` DOM walk, so commented-out examples and literal
    attribute strings shown in ``<code>`` / ``<template>`` samples are ignored
    for free (they are never real attributes).
    """
    scanner = _IdentityScanner()
    try:
        scanner.feed(html)
        scanner.close()
    except Exception:
        # A HARD gate must fail closed: a parser hiccup (near-impossible on the
        # lenient HTMLParser, but a future scanner bug would land here) is
        # reported, not silently swallowed into a green gate that could hide a
        # real mark problem.
        return [
            'the identity-v1 structure could not be checked (internal parse '
            'error) -- treating it as a failure rather than skipping the check; '
            'please report this poster.'
        ]

    state = scanner.state
    is_identity = (state is not None) or scanner.state_attr_anywhere \
        or scanner.has_contract or scanner.gen_meta
    if not is_identity:
        return []  # pre-identity legacy poster: no identity enforcement at all

    problems: list[str] = []

    # Structural integrity (state-independent): the FIRST id="psReg" element
    # must be an SVG-namespace <symbol> carrying the canonical ⊕, and every
    # mark wraps exactly one live <use> with no stray uses.
    if scanner.use_total and not scanner.symbol_seen:
        problems.append(
            'a <use href="#psReg"> references the identity glyph but no '
            '#psReg <symbol> is defined -- add the sprite <defs> block (an '
            'id="psReg" on a non-<symbol> element, or a different-case id, '
            'does not resolve).'
        )
    elif scanner.use_total and scanner.psreg_first == "other":
        problems.append(
            'another element carries id="psReg" BEFORE the sprite <symbol> -- '
            'fragment resolution takes the FIRST matching id in the document, '
            'so the duplicate shadows the sprite and <use href="#psReg"> '
            'resolves to the wrong element; remove the duplicate id.'
        )
    elif scanner.use_total and scanner.psreg_first == "symbol-html":
        problems.append(
            'the #psReg <symbol> is not inside an <svg> -- a bare <symbol> in '
            'HTML flow does not define an SVG symbol, so <use href="#psReg"> '
            'resolves to nothing; wrap it in <svg><defs>...</defs></svg>.'
        )
    elif scanner.use_total and not (
            scanner.sym_circles == 1 and scanner.sym_lines == 2
            and scanner.sym_other == 0):
        problems.append(
            'the #psReg <symbol> is empty or not the canonical ⊕ glyph '
            f'(its render path holds {scanner.sym_circles} circle(s) + '
            f'{scanner.sym_lines} line(s) + {scanner.sym_other} other '
            'drawable(s); expected exactly 1 circle + 2 lines) -- restore '
            'the sprite verbatim from a template.'
        )
    if scanner.marks_without_use:
        problems.append(
            f'{scanner.marks_without_use} identity mark(s) wrap no live '
            '<use href="#psReg"> -- every data-ps-mark must contain its glyph '
            '(<svg><use href="#psReg"/></svg>, the <use> inside the <svg>); an '
            'empty mark, or a bare <use> outside an <svg>, renders nothing.'
        )
    if scanner.marks_multi_use:
        problems.append(
            f'{scanner.marks_multi_use} identity mark(s) wrap more than one '
            '<use href="#psReg"> -- each mark is one registration glyph; keep '
            'a single <use> per data-ps-mark.'
        )
    if scanner.unknown_marks:
        problems.append(
            f'{scanner.unknown_marks} data-ps-mark element(s) carry a value '
            'other than "corner" or "woven" -- a typo\'d mark is not enforced '
            'and (under "off") can still paint a glyph; use "corner"/"woven" '
            'or remove the attribute.'
        )
    if scanner.uses_outside_mark:
        problems.append(
            f'{scanner.uses_outside_mark} live <use href="#psReg"> sit outside '
            'any data-ps-mark -- a bare glyph reference still paints the mark, '
            'so it must live inside a data-ps-mark (or be removed, e.g. when '
            'anonymizing).'
        )
    if scanner.root_mark:
        problems.append(
            'data-ps-mark sits on the poster root itself -- the root cannot '
            'be its own identity mark (any descendant <use> would satisfy its '
            'containment); put the mark on its dedicated wrapper (the '
            '.corner-sig span, or the woven host element).'
        )
    if scanner.shadow_template:
        problems.append(
            'a <template shadowrootmode=...> (declarative shadow DOM) is '
            'present -- unlike a plain inert <template>, its content DOES '
            'render, and the identity scan does not model shadow-tree '
            'scoping; inline the content instead.'
        )

    if state is None:
        if scanner.state_attr_anywhere:
            # The state attribute exists but NOT on the poster root -- a
            # misplaced state must not silently disable identity enforcement
            # (an author who wrote data-ps-identity="off" on the wrong element
            # would believe the poster is anonymous while it still marks).
            problems.append(
                'data-ps-identity is set on an element that is NOT the poster '
                'root -- move it onto the data-measure-role="poster" element; '
                'a misplaced state silently disables identity enforcement.'
            )
        else:
            # Declares itself posterly (identity-v1 contract or generator
            # <meta>) but omits the state -- a NEW poster missing its
            # identity, not legacy.
            problems.append(
                'this poster declares itself posterly (identity-v1 contract '
                'or generator meta) but has no data-ps-identity -- a posterly '
                'poster must set data-ps-identity="on" (or "off" for '
                'anonymous) on the poster root (the data-measure-role='
                '"poster" element).'
            )
        return problems

    # identity-v1 supersedes the legacy .ornament watermark. A LIVE (uncommented)
    # .ornament under an active identity contract is a problem either way: with
    # "on" it duplicates the corner mark; with "off" it leaks an identifying
    # watermark. (Commented-out / code-sample examples aren't real elements.)
    if scanner.ornament:
        problems.append(
            'a live .ornament watermark is present, but identity-v1 supersedes '
            'it -- remove the .ornament element (under "on" it duplicates the '
            'corner mark; under "off" it leaks an identifying watermark).'
        )

    if state == "on":
        if scanner.corner != 1:
            problems.append(
                f'data-ps-identity="on" requires exactly one '
                f'data-ps-mark="corner" (found {scanner.corner}) -- the corner '
                'signature is the always-on identity mark.'
            )
        elif scanner.corner_in_root != 1:
            problems.append(
                'the corner mark sits OUTSIDE the poster root '
                '(data-measure-role="poster") -- the contract places it in '
                'the root\'s bottom-right padding safe zone, and the polish '
                'visibility probe only scans the root; move it inside.'
            )
        if scanner.woven > 1:
            problems.append(
                f'found {scanner.woven} data-ps-mark="woven" elements -- at '
                'most one woven identity mark is allowed per poster.'
            )
        elif scanner.woven == 1 and scanner.woven_in_root != 1:
            problems.append(
                'the woven mark sits OUTSIDE the poster root '
                '(data-measure-role="poster") -- it must ride existing '
                'content INSIDE the poster; move it (or remove it).'
            )
        if scanner.psreg_refs != scanner.use_total:
            problems.append(
                f'{scanner.psreg_refs - scanner.use_total} #psReg '
                'reference(s) are not live, mark-wrapped instances (inside '
                '<defs>/<pattern>/<desc>, or an inert HTML-namespace <use>) '
                '-- indirect plumbing can still reach the canvas via '
                'fill="url(#...)" and paint extra glyphs; the glyph must be '
                'instanced ONLY via its marks. Delete the stray reference(s).'
            )
    elif state == "off":
        if scanner.corner or scanner.woven or scanner.psreg_refs:
            problems.append(
                f'data-ps-identity="off" (anonymous) but found {scanner.corner} '
                f'corner + {scanner.woven} woven mark(s) and '
                f'{scanner.psreg_refs} #psReg reference(s) -- anonymity must '
                'REMOVE every data-ps-mark AND every <use href="#psReg"> '
                '(including ones inside <defs>/<pattern>, which can still '
                'reach the canvas). Delete them, or set data-ps-identity="on".'
            )
    else:
        problems.append(
            f'data-ps-identity="{ascii_safe(state)}" is not a valid state '
            '(use "on" or "off", or omit the attribute for legacy posters).'
        )
    return problems


def identity_woven_missing(html: str) -> bool:
    """True iff the poster is identity ``on`` and carries NO woven mark.

    Structure-aware (via :class:`_IdentityScanner`), so a woven example inside
    a comment or an inert ``<template>`` doesn't suppress the soft polish
    advisory. False for any non-``on`` poster (legacy / anonymous /
    unparseable) -- no advisory there.
    """
    scanner = _IdentityScanner()
    try:
        scanner.feed(html)
        scanner.close()
    except Exception:
        return False
    return scanner.state == "on" and scanner.woven == 0


def cmd_preflight(args: argparse.Namespace) -> int:
    html_path = Path(args.html).resolve()
    if not html_path.exists():
        _eprint(f"ERROR: HTML not found: {ascii_safe(html_path)}")
        return 2
    raw = html_path.read_text(encoding="utf-8", errors="ignore")
    body = strip_for_lint(raw)

    problems: list[str] = []
    warnings: list[str] = []

    # 0) Unclosed <style>/<script>/<!-- --> . strip_for_lint needs the
    #    closer to remove the block, so an unclosed opener SURVIVES in
    #    `body`. A real browser swallows the rest of the document into that
    #    construct -- which makes every post-strip check below (LaTeX scan,
    #    raw-'<' scan, role-presence) untrustworthy: the linter "sees" a
    #    poster div the browser will never render. Fail loudly instead of
    #    silently PASSing on markup we can't actually see past.
    m_open = re.search(r"<!--|<style\b|<script\b", body, re.IGNORECASE)
    if m_open:
        ln = body[: m_open.start()].count("\n") + 1
        problems.append(
            f"L{ln}: unclosed '{ascii_safe(m_open.group(0))}' block -- add "
            "the matching '-->', '</style>', or '</script>'. The browser "
            "would otherwise swallow the rest of the poster into it."
        )

    # 1) LaTeX residue.
    for pat, desc in LATEX_PATTERNS:
        for m in re.finditer(pat, body):
            ln = body[: m.start()].count("\n") + 1
            problems.append(f"L{ln}: {desc} -> '{ascii_safe(m.group(0))}'")

    # 2) Raw '<' inside math segments. The common HTML-parse failure
    #    case is `a<b` / `x<y`. We catch '<' even after a letter/digit.
    #    Suppressed only when it's an escape `\<` or part of `</` / `<!`
    #    (HTML constructs MathJax never sees) or `<=` (a single MathJax
    #    token that is parsed atomically and does NOT trip the HTML
    #    tokenizer's tag-start lookahead).
    for s, e, mbody in find_math_segments(body):
        # Compute the math body's offset inside the original segment so
        # multi-line `$$ … \n a < b \n … $$` reports the `<`'s line,
        # not the segment-start line. find_math_segments hands back the
        # full `(start, end, body)` of the segment; the body's first
        # char is at `body[s + (segment_text_len - body_len)]` — easier
        # to recompute via `body.find(mbody, s)`.
        body_offset_in_body = body.find(mbody, s)
        if body_offset_in_body == -1:
            body_offset_in_body = s  # fallback shouldn't happen
        for m in re.finditer(r"(?<!\\)<(?![=/!])", mbody):
            abs_offset = body_offset_in_body + m.start()
            ln = body[: abs_offset].count("\n") + 1
            label = _delim_label(body[s:e], body[s:e])
            problems.append(
                f"L{ln}: raw '<' inside {label} "
                f"'{ascii_safe(mbody.strip()[:60])}' -- use \\lt"
            )

    # 3) Image src: local must exist; remote http(s) warns. A print
    #    poster should be self-contained -- a CDN image that 404s or is
    #    slow at render time silently breaks the figure, and the render
    #    gates can't see a missing remote image. data: URIs are inline.
    for m in re.finditer(r'src\s*=\s*["\']([^"\']+)["\']', body,
                         re.IGNORECASE):
        src = m.group(1)
        # Scheme matching is case-insensitive (browsers treat `HTTPS:` /
        # `DATA:` like `https:` / `data:`); lower-case only for the scheme
        # test, keep `src` raw for display and local-path resolution.
        src_l = src.lower()
        if src_l.startswith("data:"):
            continue
        if src_l.startswith(("http://", "https://", "//")):
            ln = body[: m.start()].count("\n") + 1
            warnings.append(
                f"L{ln}: remote image '{ascii_safe(src[:60])}' -- inline or "
                "localize "
                "it; a print poster should not depend on a CDN at render "
                "time"
            )
            continue
        # Strip ?query / #fragment and percent-decode before resolving a
        # LOCAL path -- a legit `fig.png?v=2` or `my%20fig.png` otherwise
        # reads as a missing file.
        local = unquote(urlsplit(src).path)
        candidate = (html_path.parent / local).resolve()
        if not candidate.exists():
            ln = body[: m.start()].count("\n") + 1
            problems.append(f"L{ln}: missing local image '{ascii_safe(src)}'")

    # 4) data-measure-role="poster" required on the root.
    if not re.search(r'data-measure-role\s*=\s*["\']poster["\']', body):
        problems.append(
            'missing required data-measure-role="poster" on root'
        )

    # 5) Unknown role values flag silent measure misses.
    for m in re.finditer(
        r'data-measure-role\s*=\s*["\']([^"\']+)["\']', body
    ):
        role = m.group(1).strip()
        if role not in KNOWN_ROLES:
            ln = body[: m.start()].count("\n") + 1
            problems.append(
                f"L{ln}: unknown data-measure-role='{ascii_safe(role)}' "
                f"(allowed: {sorted(KNOWN_ROLES)})"
            )

    # 6) Role nesting: each role must sit inside its required parent
    #    role per ROLE_PARENTS. The precipitating bug was a misplaced
    #    `</div>` that closed `.poster` early -- the count of opens and
    #    closes was still balanced (the extra `</div>` made some other
    #    legitimate close stray), but `footer-strip` ended up outside
    #    the grid so its row collapsed to 0 px. Catching it requires
    #    looking at the parent role of every role-bearing element, not
    #    just the totals.
    #
    #    Stray closer detection is intentionally NOT enforced here:
    #    HTMLParser's recovery (and the browser's) eagerly rebalances
    #    in ways that mask which `</tag>` was actually misplaced, so a
    #    naive "stray close" count fires on the wrong line. The
    #    parent-role check below catches the *visible symptom* (a role
    #    in the wrong layout slot) which is what measure would
    #    eventually report off-canvas anyway.
    #
    #    Note: the parser is fed RAW html (script/style intact) -- it
    #    already skips inside `<script>` and `<style>` properly.
    role_records, _stray = check_role_nesting(raw)
    for role, parent, ln, _tag in role_records:
        expected = ROLE_PARENTS.get(role)
        if not expected:
            continue
        if parent not in expected:
            shown_parent = parent if parent is not None else "(document root)"
            problems.append(
                f"L{ln}: data-measure-role='{ascii_safe(role)}' is nested "
                f"inside {ascii_safe(shown_parent)}; expected parent role "
                f"in {sorted(expected)}. A misplaced `</div>` is the usual "
                "cause -- it closes a grid container early so the role "
                "ends up outside its layout slot."
            )

    # 7) Every `.figure` block should carry a non-empty `.caption`
    #    (figure-card contract: `.figure > img + .caption`). A bare,
    #    unlabeled figure is a recurring authoring defect. Warn, don't
    #    fail: the captionless banner-figure / hero stage don't carry
    #    the `figure` class token and are never scanned.
    for ln in figures_missing_caption(raw):
        warnings.append(
            f"L{ln}: .figure block has no non-empty .caption -- every "
            "paper figure carries a one-line caption (figure-card "
            "contract in COMPONENTS.md); an unlabeled figure reads as "
            "a defect. Write a short factual one-liner or drop the "
            "figure."
        )

    # 8) Soft sanity: no <title> / no <h1>. Warns, doesn't fail.
    if not re.search(r"<title[^>]*>.+?</title>", raw, re.DOTALL):
        warnings.append("no <title> set")
    if not re.search(r"<h1\b", raw):
        warnings.append(
            "no <h1> -- poster title block usually carries one"
        )

    # 9) Identity-mark (identity-v1) contract: presence / count / anonymity
    #    reverse-check / referential integrity. No-op on legacy posters that
    #    predate the contract (no data-ps-identity attribute).
    problems.extend(identity_mark_problems(raw))

    print(f"[preflight] {ascii_safe(html_path)}")
    print(f"  problems: {len(problems)}   warnings: {len(warnings)}")
    for w in warnings:
        print(f"  WARN: {w}")
    for p in problems:
        _eprint(f"  FAIL: {p}")

    if problems:
        return 1
    print("[preflight] PASS")
    return 0


def has_required_roles_in_html(html_path: Path) -> dict[str, int]:
    """Cheap static count of each known role on disk. Used by ``polish``
    so it can hard-fail on a poster lacking ALL measurement markup,
    instead of silently PASSing on "0 figures, 0 columns, 0 stat
    elements"."""
    raw = html_path.read_text(encoding="utf-8", errors="ignore")
    body = strip_for_lint(raw)
    counts: dict[str, int] = {role: 0 for role in KNOWN_ROLES}
    for m in re.finditer(
        r'data-measure-role\s*=\s*["\']([^"\']+)["\']', body
    ):
        role = m.group(1).strip()
        if role in counts:
            counts[role] += 1
    return counts
