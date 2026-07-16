"""Unit tests for the ``"dark_ground"`` --tokens declaration (style rule 12).

Covers ``resolve_dark_ground``'s parsing semantics, the CLI wiring that
forwards the parsed value into ``run_render_gate`` (mocked — no browser),
and ``run_gates``'s preservation of resolver stderr warnings once a JSON
sidecar exists. The waiver branch inside ``run_render_gate`` itself is
straight-line detail formatting on top of that forwarded flag.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import run_gates  # noqa: E402  (tools/ on sys.path via conftest)
import style_check  # noqa: E402
from style_check import resolve_dark_ground  # noqa: E402


def _pack(tmp_path: Path, payload: dict[str, object]) -> Path:
    p = tmp_path / "tokens.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_no_tokens_path_is_undeclared() -> None:
    assert resolve_dark_ground(None) is False


def test_missing_file_is_undeclared(tmp_path: Path) -> None:
    assert resolve_dark_ground(tmp_path / "absent.json") is False


def test_missing_key_is_undeclared(tmp_path: Path) -> None:
    assert resolve_dark_ground(_pack(tmp_path, {"accent": {}})) is False


def test_true_declares(tmp_path: Path) -> None:
    assert resolve_dark_ground(_pack(tmp_path, {"dark_ground": True})) is True


def test_false_is_undeclared(tmp_path: Path) -> None:
    assert resolve_dark_ground(_pack(tmp_path, {"dark_ground": False})) is False


def test_non_boolean_rejected_loudly(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for bad in ("yes", "true", 1, None):
        got = resolve_dark_ground(_pack(tmp_path, {"dark_ground": bad}))
        assert got is False
        err = capsys.readouterr().err
        assert "dark_ground" in err and "boolean" in err


def test_cli_forwards_dark_ground_to_render_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The parsed declaration must reach run_render_gate (no browser)."""
    html = tmp_path / "poster.html"
    html.write_text(
        "<style>@page { size: 60in 36in }</style><div>stub</div>",
        encoding="utf-8",
    )
    pack = _pack(tmp_path, {"dark_ground": True})
    seen: dict[str, bool] = {}

    def fake_render(
        html_path: Path,
        hue_centers: dict[str, float],
        dark_ground: bool = False,
        **kw: object,
    ) -> tuple[list[object], None]:
        seen["dark_ground"] = dark_ground
        return [], None

    monkeypatch.setattr(style_check, "run_render_gate", fake_render)
    style_check.main([
        str(html), "--tokens", str(pack),
        "--json", str(tmp_path / "out.json"),
    ])
    assert seen["dark_ground"] is True


def test_human_summary_prints_stderr_warnings(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The terminal digest must surface gate_stderr_warnings lines."""
    report = {
        "poster_html": "poster.html",
        "canvas": {"width_cm": None, "source": "none"},
        "gates": [{
            "name": "style", "severity": "hard", "status": "PASS",
            "summary": {"gate_stderr_warnings": ["WARNING: bad field"]},
        }],
        "overall": "PASS", "hard_failures": 0, "warnings": 0,
    }
    run_gates._print_human_summary(report)  # noqa: SLF001
    out = capsys.readouterr().out
    assert "! WARNING: bad field" in out


def test_run_gates_keeps_sidecar_stderr_warnings(tmp_path: Path) -> None:
    """A style JSON sidecar must not swallow resolver WARNING lines."""
    sidecar = tmp_path / "style_check.json"
    sidecar.write_text(json.dumps({"gate": "style", "rules": []}),
                       encoding="utf-8")
    stderr = ("WARNING: --tokens key 'dark_ground' must be a JSON boolean, "
              "got 'yes'; treating as false (not declared).")
    obj, artifacts = run_gates._summarize_gate(  # noqa: SLF001
        gate="style", returncode=0, stdout="", stderr=stderr,
        report_json_dir=tmp_path,
    )
    assert obj["gate_stderr_warnings"] == [stderr]
    assert str(sidecar) in artifacts
