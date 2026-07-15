"""Unit tests for ``run_gates``'s orchestration logic around measure's
circuit breaker (exit 3) and the marker-aware measure summary. Child
processes are monkeypatched -- no Chromium, no subprocesses.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import run_gates  # noqa: E402


def test_rc3_maps_to_hard_fail() -> None:
    """Exit 3 (circuit breaker) is a hard stop, NOT an environment
    SKIPPED -- the pre-rework mapping sent every rc!=0/1 to SKIPPED."""
    assert run_gates._status_from_returncode(3, "hard") == "FAIL"
    assert run_gates._status_from_returncode(2, "hard") == "SKIPPED"
    assert run_gates._status_from_returncode(1, "hard") == "FAIL"
    assert run_gates._status_from_returncode(0, "hard") == "PASS"


def test_measure_tail_keeps_marker_block() -> None:
    stdout = "\n".join(
        ["[measure] columns found: 3"]
        + [f"noise {i}" for i in range(20)]
        + ["[measure] suggested adjustments:",
           "  shared passing band: 3078..3082 px",
           "  col0  3080.00 px -> keep",
           "[measure] edit targets -- cards per column, top-to-bottom.",
           "    card#0 L142 h=611px \"1 Motivation\"",
           "[measure] FAIL -- alignment gate not met"]
    )
    tail = run_gates._measure_tail(stdout)
    assert "shared passing band" in tail
    assert "edit targets" in tail
    assert "card#0" in tail
    # The generic 8-line tail would have dropped the adjustments header.
    assert "[measure] suggested adjustments:" in tail


def test_measure_tail_caps_long_block() -> None:
    stdout = "\n".join(
        ["[measure] edit targets -- cards per column, top-to-bottom."]
        + [f"    card#{i}" for i in range(200)]
        + ["[measure] FAIL -- alignment gate not met"]
    )
    tail = run_gates._measure_tail(stdout, cap=40)
    assert len(tail.splitlines()) <= 41  # cap + elision marker line
    assert "(truncated)" in tail
    # Verdict tail survives the elision.
    assert "FAIL -- alignment gate not met" in tail


def test_measure_tail_fallback_without_marker() -> None:
    stdout = "\n".join(f"line {i}" for i in range(30))
    tail = run_gates._measure_tail(stdout)
    assert len(tail.splitlines()) == run_gates.TAIL_LINES


def _gate_of(argv: list) -> str:
    """Recover the gate from the child argv STRUCTURALLY (script name /
    subcommand), never by substring-matching the whole argv -- the html
    lives under a pytest tmp dir whose name can contain gate words
    (e.g. `test_plain_measure_fail...`)."""
    script = Path(str(argv[1])).name
    if script == "style_check.py":
        return "style"
    if script == "asset_check.py":
        return "asset"
    if script == "poster_check.py":
        return str(argv[2])
    return script


def _opts(**kw) -> argparse.Namespace:
    base = dict(
        report=None, fail_fast=False, strict_polish=False, tokens=None,
        manifest=None, hero=False, waive_total_area=False,
        no_render=False, style_disable="4,5", measure_budget=None,
        reset_measure_budget=False,
    )
    base.update(kw)
    return argparse.Namespace(**base)


def test_breaker_halts_remaining_gates(
    monkeypatch, tmp_path: Path
) -> None:
    """measure exit 3 stops the run even WITHOUT --fail-fast: polish
    must not burn another render after the banner said stop."""
    html = tmp_path / "poster.html"
    html.write_text("<html></html>", encoding="utf-8")
    ran: list[str] = []

    def fake_run_child(argv, cwd):
        gate = _gate_of(argv)
        ran.append(gate)
        if gate == "measure":
            return 3, "CIRCUIT BREAKER -- 30/30 consecutive failed", ""
        return 0, f"[{gate}] PASS", ""

    monkeypatch.setattr(run_gates, "_run_child", fake_run_child)
    report = run_gates.run_all(html, _opts())

    assert "polish" not in ran
    by_name = {g["name"]: g for g in report["gates"]}
    assert by_name["measure"]["status"] == "FAIL"
    assert by_name["polish"]["status"] == "SKIPPED"
    assert "circuit breaker" in str(
        by_name["polish"]["summary"]
    ).lower()
    assert report["overall"] == "FAIL"


def test_plain_measure_fail_still_runs_polish(
    monkeypatch, tmp_path: Path
) -> None:
    """A normal measure FAIL (rc=1) keeps the accumulate behaviour --
    the report should still show the whole fix surface."""
    html = tmp_path / "poster.html"
    html.write_text("<html></html>", encoding="utf-8")
    ran: list[str] = []

    def fake_run_child(argv, cwd):
        gate = _gate_of(argv)
        ran.append(gate)
        if gate == "measure":
            return 1, "[measure] FAIL", ""
        return 0, f"[{gate}] PASS", ""

    monkeypatch.setattr(run_gates, "_run_child", fake_run_child)
    report = run_gates.run_all(html, _opts())
    assert "polish" in ran
    assert report["overall"] == "FAIL"


def test_budget_flags_forwarded() -> None:
    argv = run_gates._build_argv(
        "measure", Path("/x"), Path("/y/poster.html"),
        _opts(measure_budget=12, reset_measure_budget=True),
        Path("/y"),
    )
    assert "--measure-budget" in argv and "12" in argv
    assert "--reset-budget" in argv


def test_budget_flags_omitted_by_default() -> None:
    argv = run_gates._build_argv(
        "measure", Path("/x"), Path("/y/poster.html"), _opts(), Path("/y"),
    )
    assert "--measure-budget" not in argv
    assert "--reset-budget" not in argv
