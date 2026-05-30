"""Round-10: polish's terminal output must stay ASCII even when the
USER's HTML contains Unicode (orphan glyphs, image src), and a broken /
zero-natural-size <img> must surface a FIG/BROKEN warning rather than be
silently skipped. Playwright is mocked via an injected fake module, with
page.evaluate() returning canned polish data."""
from __future__ import annotations

import argparse
import sys
import types

from _posterly import polish as _polish
from _posterly.textutil import ascii_safe


# Canned _POLISH_JS result: one broken figure (zero natural size) + one
# orphan whose text carries Unicode that must NOT reach stdout raw.
_DATA = {
    "figures": [
        {"src": "https://cdn.example.com/broken.png",
         "rendered_w": 100.0, "card_w": 200.0,
         "natural_w": 0.0, "natural_h": 0.0},
    ],
    "orphans": [
        {"text": "1.18–1.30× ↑", "ws": "",
         "tag": "span", "cls": "stat-num"},
    ],
    "cols": [],
}


def _install_fake_playwright(monkeypatch):
    class _PW:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    mod = types.ModuleType("playwright.sync_api")
    mod.TimeoutError = type("_T", (Exception,), {})
    mod.sync_playwright = lambda: _PW()
    parent = types.ModuleType("playwright")
    parent.sync_api = mod
    monkeypatch.setitem(sys.modules, "playwright", parent)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", mod)


class _Page:
    def goto(self, *a, **k):
        pass

    def evaluate(self, *a, **k):
        return _DATA


class _Browser:
    def close(self):
        pass


def _poster_html(tmp_path):
    p = tmp_path / "poster.html"
    p.write_text(
        "<html><head><style>@page { size: 24in 36in }</style></head>"
        "<body><div data-measure-role=\"poster\">"
        "<div data-measure-role=\"column\">"
        "<div data-measure-role=\"card\"></div></div></div></body></html>",
        encoding="utf-8",
    )
    return p


def _args(html):
    return argparse.Namespace(
        html=str(html), canvas=None, settle_ms=500,
        mathjax_timeout_ms=15000, wide_min_ratio=0.65,
        tall_max_ratio=0.70, square_min_ratio=0.55,
        max_space_between_fill=0.05, strict=False,
    )


def test_ascii_safe_escapes_non_ascii() -> None:
    s = ascii_safe("a × b ↑ –")
    s.encode("ascii")  # must not raise
    assert "×" not in s and "↑" not in s
    assert ascii_safe("plain ascii") == "plain ascii"


def test_polish_output_ascii_and_flags_broken_image(
    tmp_path, monkeypatch, capsys
) -> None:
    _install_fake_playwright(monkeypatch)
    monkeypatch.setattr(
        _polish._render, "open_print_emulated_page",
        lambda p, vp: (_Browser(), None, _Page()),
    )
    monkeypatch.setattr(_polish._render, "settle_page", lambda *a, **k: object())
    monkeypatch.setattr(
        _polish._render, "hard_fail_on_settle_problems", lambda *a, **k: None
    )
    rc = _polish.cmd_polish(_args(_poster_html(tmp_path)))
    combined = "".join(capsys.readouterr())
    combined.encode("ascii")  # raises if user Unicode leaked through
    assert "FIG/BROKEN" in combined          # zero-size img surfaced
    assert "ORPHAN" in combined              # orphan still detected
    assert "↑" not in combined and "×" not in combined  # escaped
    assert rc == 0                           # warnings only (not --strict)
