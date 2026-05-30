"""verify-final tests: --canvas vs --from-html mutual-exclusion +
missing-input behaviour, plus pdfinfo parsing / dimension-and-rotation
logic via a monkeypatched pdfinfo (no Poppler needed). The end-to-end
pdfinfo round-trip on a real PDF is covered by a Poppler-gated
integration test against the hello_world example."""
from __future__ import annotations

import argparse
import shutil

import pytest

from _posterly import verify_final


def _args(**over):
    base = argparse.Namespace(
        pdf="nonexistent.pdf",
        canvas=None,
        from_html=None,
        dim_tol_in=0.05,
        max_size_mb=20.0,
        allow_rotated=False,
    )
    for k, v in over.items():
        setattr(base, k, v)
    return base


def test_missing_pdf_returns_2(tmp_path) -> None:
    rc = verify_final.cmd_verify_final(_args(pdf=str(tmp_path / "missing.pdf")))
    assert rc == 2


def test_neither_canvas_nor_from_html_returns_2(tmp_path) -> None:
    """The old default was --canvas=60x36in, which silently passed
    a 24x36in poster as wrong-sized. Now both are None → exit 2 with a
    clear message."""
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"not really a pdf")
    rc = verify_final.cmd_verify_final(_args(pdf=str(pdf)))
    assert rc == 2


def test_both_canvas_and_from_html_returns_2(tmp_path) -> None:
    """Mutually exclusive — supplying both should fail-fast rather
    than silently preferring one."""
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"not really a pdf")
    html = tmp_path / "y.html"
    html.write_text(
        "<html><head><style>@page { size: 36in 47in }</style>"
        "</head></html>", encoding="utf-8",
    )
    rc = verify_final.cmd_verify_final(
        _args(pdf=str(pdf), canvas=(36.0, 47.0), from_html=str(html))
    )
    assert rc == 2


def test_from_html_missing_path_returns_2(tmp_path) -> None:
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"not really a pdf")
    rc = verify_final.cmd_verify_final(
        _args(pdf=str(pdf), from_html=str(tmp_path / "missing.html"))
    )
    assert rc == 2


def test_from_html_with_no_page_returns_2(tmp_path) -> None:
    """When --from-html points to a file without an @page rule, fail
    cleanly rather than silently fall back to a default canvas."""
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"not really a pdf")
    html = tmp_path / "y.html"
    html.write_text("<html><body>no @page here</body></html>",
                    encoding="utf-8")
    rc = verify_final.cmd_verify_final(
        _args(pdf=str(pdf), from_html=str(html))
    )
    assert rc == 2


# --- pdfinfo parsing / dimension comparison (monkeypatched, no Poppler) ---


def _pdfinfo(pages=1, w_pts=1728.0, h_pts=2592.0, rot=0):
    """Canned `pdfinfo` stdout. 1728x2592 pts == 24x36 in."""
    return (
        f"Pages:          {pages}\n"
        f"Page size:      {w_pts} x {h_pts} pts\n"
        f"Page rot:       {rot}\n"
    )


def _real_pdf(tmp_path, nbytes=1024):
    pdf = tmp_path / "poster.pdf"
    pdf.write_bytes(b"%PDF-1.7\n" + b"0" * max(0, nbytes - 9))
    return pdf


def _patch_pdfinfo(monkeypatch, text=None, exc=None):
    def fake(*a, **k):
        if exc is not None:
            raise exc
        return text
    monkeypatch.setattr(verify_final.subprocess, "check_output", fake)


def test_correct_dimensions_pass(tmp_path, monkeypatch) -> None:
    pdf = _real_pdf(tmp_path)
    _patch_pdfinfo(monkeypatch, _pdfinfo())  # 24x36in, 1 page, rot 0
    rc = verify_final.cmd_verify_final(_args(pdf=str(pdf), canvas=(24.0, 36.0)))
    assert rc == 0


def test_dimension_mismatch_fails(tmp_path, monkeypatch) -> None:
    pdf = _real_pdf(tmp_path)
    _patch_pdfinfo(monkeypatch, _pdfinfo(h_pts=2000.0))  # wrong height
    rc = verify_final.cmd_verify_final(_args(pdf=str(pdf), canvas=(24.0, 36.0)))
    assert rc == 1


def test_swapped_dims_rejected_without_rotation(tmp_path, monkeypatch) -> None:
    """36x24 PDF vs 24x36 canvas, page rot 0, no --allow-rotated → FAIL."""
    pdf = _real_pdf(tmp_path)
    _patch_pdfinfo(monkeypatch, _pdfinfo(w_pts=2592.0, h_pts=1728.0))
    rc = verify_final.cmd_verify_final(_args(pdf=str(pdf), canvas=(24.0, 36.0)))
    assert rc == 1


def test_swapped_dims_accepted_with_allow_rotated(tmp_path, monkeypatch) -> None:
    pdf = _real_pdf(tmp_path)
    _patch_pdfinfo(monkeypatch, _pdfinfo(w_pts=2592.0, h_pts=1728.0))
    rc = verify_final.cmd_verify_final(
        _args(pdf=str(pdf), canvas=(24.0, 36.0), allow_rotated=True)
    )
    assert rc == 0


def test_swapped_dims_accepted_when_page_rotated(tmp_path, monkeypatch) -> None:
    """Page rot 90 legitimizes the swap even without --allow-rotated."""
    pdf = _real_pdf(tmp_path)
    _patch_pdfinfo(monkeypatch, _pdfinfo(w_pts=2592.0, h_pts=1728.0, rot=90))
    rc = verify_final.cmd_verify_final(_args(pdf=str(pdf), canvas=(24.0, 36.0)))
    assert rc == 0


def test_wrong_page_count_fails(tmp_path, monkeypatch) -> None:
    pdf = _real_pdf(tmp_path)
    _patch_pdfinfo(monkeypatch, _pdfinfo(pages=2))
    rc = verify_final.cmd_verify_final(_args(pdf=str(pdf), canvas=(24.0, 36.0)))
    assert rc == 1


def test_oversize_file_fails(tmp_path, monkeypatch) -> None:
    """Dimensions correct but file over --max-size-mb → FAIL."""
    pdf = _real_pdf(tmp_path)
    _patch_pdfinfo(monkeypatch, _pdfinfo())
    rc = verify_final.cmd_verify_final(
        _args(pdf=str(pdf), canvas=(24.0, 36.0), max_size_mb=0.0)
    )
    assert rc == 1


def test_unparseable_page_size_fails(tmp_path, monkeypatch) -> None:
    pdf = _real_pdf(tmp_path)
    _patch_pdfinfo(
        monkeypatch,
        "Pages:          1\nPage size:      letter\nPage rot:       0\n",
    )
    rc = verify_final.cmd_verify_final(_args(pdf=str(pdf), canvas=(24.0, 36.0)))
    assert rc == 1


def test_pdfinfo_missing_returns_2(tmp_path, monkeypatch) -> None:
    pdf = _real_pdf(tmp_path)
    _patch_pdfinfo(monkeypatch, exc=FileNotFoundError("pdfinfo"))
    rc = verify_final.cmd_verify_final(_args(pdf=str(pdf), canvas=(24.0, 36.0)))
    assert rc == 2


def test_failure_output_is_ascii(tmp_path, monkeypatch, capsys) -> None:
    """Round-8: runtime stdout/stderr on a FAIL must be ASCII-clean
    (no +/-, x, deg, -> mojibake when pasted into CI logs / issues)."""
    pdf = _real_pdf(tmp_path)
    _patch_pdfinfo(monkeypatch, _pdfinfo(w_pts=2592.0, h_pts=1728.0))
    rc = verify_final.cmd_verify_final(_args(pdf=str(pdf), canvas=(24.0, 36.0)))
    assert rc == 1
    out = capsys.readouterr()
    (out.out + out.err).encode("ascii")  # raises UnicodeEncodeError if not


@pytest.mark.skipif(
    shutil.which("pdfinfo") is None,
    reason="poppler/pdfinfo not installed",
)
def test_hello_world_pdf_real_pdfinfo() -> None:
    """Round-10: exercise the REAL pdfinfo round-trip on the shipped
    example PDF (no monkeypatch) — this is the integration coverage the
    README/docstring refer to. Skipped when poppler is absent."""
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    pdf = root / "examples" / "hello_world" / "poster_preview.pdf"
    html = root / "examples" / "hello_world" / "poster.html"
    if not pdf.exists():
        pytest.skip(
            "example PDF is a gitignored build artifact -- run the "
            "hello_world render step to generate it"
        )
    assert html.exists(), f"example HTML missing at {html}"
    rc = verify_final.cmd_verify_final(
        _args(pdf=str(pdf), from_html=str(html))
    )
    assert rc == 0
