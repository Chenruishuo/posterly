"""Wiring tests for the circuit breaker inside ``cmd_measure`` -- the
geometry pass is monkeypatched, so these run without Chromium.

Pinned semantics:

- consecutive rc=1 *measured* failures increment; the cap trips exit 3,
- a PASS clears the state file,
- an UNmeasured failure (nav timeout / settle fail) does NOT count,
- an exhausted budget refuses BEFORE rendering (pre-render exit 3),
- ``--reset-budget`` starts fresh; ``--measure-budget 0`` disables,
- rc=2 usage errors never touch the counter.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from _posterly import budget as B
from _posterly import measure as _measure


def _args(html: Path, **kw) -> argparse.Namespace:
    ns = argparse.Namespace(html=str(html))
    for k, v in kw.items():
        setattr(ns, k, v)
    return ns


def _fake_once(rc: int, measured: bool):
    calls = []

    def fake(args, html_path):
        calls.append(1)
        return rc, measured

    return fake, calls


def test_consecutive_failures_trip_breaker(monkeypatch, tmp_path) -> None:
    html = tmp_path / "poster.html"
    html.write_text("<html></html>", encoding="utf-8")
    fake, _ = _fake_once(1, True)
    monkeypatch.setattr(_measure, "_measure_once", fake)

    a = _args(html, measure_budget=2)
    assert _measure.cmd_measure(a) == 1            # failure 1/2
    assert _measure.cmd_measure(a) == B.EXIT_BUDGET_EXHAUSTED  # 2/2 trips


def test_exhausted_budget_refuses_pre_render(
    monkeypatch, tmp_path
) -> None:
    html = tmp_path / "poster.html"
    html.write_text("<html></html>", encoding="utf-8")
    fake, calls = _fake_once(1, True)
    monkeypatch.setattr(_measure, "_measure_once", fake)

    a = _args(html, measure_budget=1)
    assert _measure.cmd_measure(a) == B.EXIT_BUDGET_EXHAUSTED  # 1/1
    n_calls = len(calls)
    # Next call must refuse WITHOUT running the geometry pass again.
    assert _measure.cmd_measure(a) == B.EXIT_BUDGET_EXHAUSTED
    assert len(calls) == n_calls


def test_pass_clears_state(monkeypatch, tmp_path) -> None:
    html = tmp_path / "poster.html"
    html.write_text("<html></html>", encoding="utf-8")
    fail, _ = _fake_once(1, True)
    monkeypatch.setattr(_measure, "_measure_once", fail)
    a = _args(html, measure_budget=5)
    _measure.cmd_measure(a)
    assert B.budget_path(html).exists()

    ok, _ = _fake_once(0, True)
    monkeypatch.setattr(_measure, "_measure_once", ok)
    assert _measure.cmd_measure(a) == 0
    assert not B.budget_path(html).exists()


def test_unmeasured_failure_does_not_count(
    monkeypatch, tmp_path
) -> None:
    html = tmp_path / "poster.html"
    html.write_text("<html></html>", encoding="utf-8")
    fake, _ = _fake_once(1, False)  # e.g. nav timeout
    monkeypatch.setattr(_measure, "_measure_once", fake)
    a = _args(html, measure_budget=1)
    assert _measure.cmd_measure(a) == 1
    assert _measure.cmd_measure(a) == 1  # would be 3 if it counted
    assert not B.budget_path(html).exists()


def test_rc2_does_not_count(monkeypatch, tmp_path) -> None:
    html = tmp_path / "poster.html"
    html.write_text("<html></html>", encoding="utf-8")
    fake, _ = _fake_once(2, False)
    monkeypatch.setattr(_measure, "_measure_once", fake)
    a = _args(html, measure_budget=1)
    assert _measure.cmd_measure(a) == 2
    assert not B.budget_path(html).exists()


def test_reset_budget_flag(monkeypatch, tmp_path) -> None:
    html = tmp_path / "poster.html"
    html.write_text("<html></html>", encoding="utf-8")
    fake, calls = _fake_once(1, True)
    monkeypatch.setattr(_measure, "_measure_once", fake)

    a = _args(html, measure_budget=1)
    assert _measure.cmd_measure(a) == B.EXIT_BUDGET_EXHAUSTED
    # Fresh start: measures again (once) instead of refusing.
    a2 = _args(html, measure_budget=1, reset_budget=True)
    n = len(calls)
    assert _measure.cmd_measure(a2) == B.EXIT_BUDGET_EXHAUSTED  # 1/1 again
    assert len(calls) == n + 1


def test_reset_failure_disables_breaker_for_run(
    monkeypatch, tmp_path
) -> None:
    """--reset-budget whose cleanup fails outright (removal AND the
    zero-write fallback) must disable the breaker for this run: we
    just promised a fresh start, so the stale count may not fire a
    phantom pre-render refusal."""
    html = tmp_path / "poster.html"
    html.write_text("<html></html>", encoding="utf-8")
    fake, calls = _fake_once(1, True)
    monkeypatch.setattr(_measure, "_measure_once", fake)

    a = _args(html, measure_budget=1)
    assert _measure.cmd_measure(a) == B.EXIT_BUDGET_EXHAUSTED  # 1/1

    monkeypatch.setattr(B, "clear", lambda *a, **kw: "simulated failure")
    a2 = _args(html, measure_budget=1, reset_budget=True)
    n = len(calls)
    assert _measure.cmd_measure(a2) == 1  # measured; no breaker at all
    assert len(calls) == n + 1


def test_pass_zeroes_count_even_when_unlink_fails(
    monkeypatch, tmp_path
) -> None:
    """A PASS with a state file that cannot be removed still resets
    the count (zero-write fallback) -- the next failing run starts
    from 1, not from the pre-PASS history."""
    html = tmp_path / "poster.html"
    html.write_text("<html></html>", encoding="utf-8")
    bpath = B.budget_path(html)
    fail, _ = _fake_once(1, True)
    monkeypatch.setattr(_measure, "_measure_once", fail)
    a = _args(html, measure_budget=2)
    assert _measure.cmd_measure(a) == 1  # count 1/2

    real_unlink = Path.unlink

    def deny(self: Path, *args, **kw):
        if self == bpath:
            raise PermissionError("simulated: locked state file")
        return real_unlink(self, *args, **kw)

    monkeypatch.setattr(Path, "unlink", deny)
    ok, _ = _fake_once(0, True)
    monkeypatch.setattr(_measure, "_measure_once", ok)
    assert _measure.cmd_measure(a) == 0
    assert bpath.exists()  # couldn't be removed ...
    count, _warn = B.load_count(bpath, html.name)
    assert count == 0      # ... but WAS zeroed in place

    monkeypatch.setattr(_measure, "_measure_once", fail)
    assert _measure.cmd_measure(a) == 1  # 1/2 again, NOT 2/2


def test_budget_zero_disables(monkeypatch, tmp_path) -> None:
    html = tmp_path / "poster.html"
    html.write_text("<html></html>", encoding="utf-8")
    fake, _ = _fake_once(1, True)
    monkeypatch.setattr(_measure, "_measure_once", fake)
    a = _args(html, measure_budget=0)
    for _i in range(5):
        assert _measure.cmd_measure(a) == 1
    assert not B.budget_path(html).exists()


def test_missing_html_is_rc2_untouched_budget(tmp_path) -> None:
    a = _args(tmp_path / "nope.html", measure_budget=1)
    assert _measure.cmd_measure(a) == 2


# ---- measure --with-polish wiring ----------------------------------------

def test_with_polish_flag_parses_and_defaults_off() -> None:
    import poster_check
    p = poster_check.build_parser()
    a = p.parse_args(["measure", "x.html"])
    assert a.with_polish is False
    a = p.parse_args(["measure", "x.html", "--with-polish"])
    assert a.with_polish is True


def test_polish_parser_defaults_track_module_constants() -> None:
    """poster_check's polish `default=` must point at the polish-module
    constants, so `measure --with-polish` (default_polish_args) and the
    standalone `polish` command can never drift apart."""
    import poster_check
    from _posterly import polish as _polish
    a = poster_check.build_parser().parse_args(["polish", "x.html"])
    d = _polish.default_polish_args()
    assert a.wide_min_ratio == d.wide_min_ratio
    assert a.tall_max_ratio == d.tall_max_ratio
    assert a.square_min_ratio == d.square_min_ratio
    assert a.max_space_between_fill == d.max_space_between_fill
    assert a.max_card_trailing == d.max_card_trailing
    assert d.strict is False


def test_advisory_polish_skips_without_roles(tmp_path, capsys) -> None:
    """The merged pass must degrade to a printed skip -- never raise into
    the hard gate -- when the poster lacks polish's required roles."""
    from _posterly import polish as _polish
    f = tmp_path / "p.html"
    f.write_text("<html><body><div>no roles</div></body></html>")
    _polish.advisory_polish_on_page(page=None, html_path=f)
    err = capsys.readouterr().err
    assert "skipping polish pass" in err
