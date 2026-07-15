"""Unit tests for ``_posterly.budget`` -- the measure-loop circuit
breaker state. All pure-ish file I/O against tmp_path; no Chromium.

The invariants that matter:

- per-poster isolation (two HTML files in one dir never share a file),
- PASS-resets semantics live in the caller, but the state layer must
  round-trip counts faithfully and degrade to 0 + warning on anything
  implausible (corrupt JSON, future timestamp, wrong schema),
- a stale file (previous working session) silently resets,
- I/O failure warns instead of raising -- the geometry gate must never
  die because a state file couldn't be written.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from _posterly import budget as B


NOW = dt.datetime(2026, 7, 15, 12, 0, 0, tzinfo=dt.timezone.utc)


def test_budget_path_is_per_poster(tmp_path: Path) -> None:
    a = B.budget_path(tmp_path / "poster.html")
    b = B.budget_path(tmp_path / "draft.html")
    assert a != b
    assert a.parent == b.parent == tmp_path
    # Full-name keying: .html vs .htm must not collide on the stem.
    assert B.budget_path(tmp_path / "poster.htm") != a


def test_poster_name_mismatch_resets_with_warning(
    tmp_path: Path,
) -> None:
    """A state file whose recorded poster differs from the caller's is
    someone else's history (renamed file, hand-copied state) -- reset
    rather than inherit its count."""
    p = B.budget_path(tmp_path / "poster.html")
    B.record_failure(p, "other.html", 9, NOW)
    count, warn = B.load_count(p, "poster.html", NOW)
    assert count == 0 and warn is not None


def test_missing_file_is_zero_no_warning(tmp_path: Path) -> None:
    count, warn = B.load_count(
        tmp_path / ".poster.posterly_budget.json", "poster.html", NOW
    )
    assert count == 0 and warn is None


def test_roundtrip_and_clear(tmp_path: Path) -> None:
    p = B.budget_path(tmp_path / "poster.html")
    assert B.record_failure(p, "poster.html", 7, NOW) is None
    count, warn = B.load_count(p, "poster.html", NOW)
    assert count == 7 and warn is None
    B.clear(p)
    assert not p.exists()
    B.clear(p)  # idempotent on a missing file


def test_corrupt_json_resets_with_warning(tmp_path: Path) -> None:
    p = B.budget_path(tmp_path / "poster.html")
    p.write_text("{not json", encoding="utf-8")
    count, warn = B.load_count(p, "poster.html", NOW)
    assert count == 0 and warn is not None


def test_wrong_schema_resets_with_warning(tmp_path: Path) -> None:
    p = B.budget_path(tmp_path / "poster.html")
    p.write_text(json.dumps({
        "schema_version": 99, "count": 5,
        "updated": NOW.isoformat(),
    }), encoding="utf-8")
    count, warn = B.load_count(p, "poster.html", NOW)
    assert count == 0 and warn is not None


def test_negative_count_resets_with_warning(tmp_path: Path) -> None:
    p = B.budget_path(tmp_path / "poster.html")
    B.record_failure(p, "poster.html", 3, NOW)
    data = json.loads(p.read_text())
    data["count"] = -2
    p.write_text(json.dumps(data), encoding="utf-8")
    count, warn = B.load_count(p, "poster.html", NOW)
    assert count == 0 and warn is not None


def test_future_timestamp_resets_with_warning(tmp_path: Path) -> None:
    p = B.budget_path(tmp_path / "poster.html")
    B.record_failure(p, "poster.html", 5, NOW + dt.timedelta(hours=2))
    count, warn = B.load_count(p, "poster.html", NOW)
    assert count == 0 and warn is not None


def test_small_clock_skew_tolerated(tmp_path: Path) -> None:
    """A couple of minutes of skew is normal (NTP drift, FS timestamps);
    only implausible future stamps reset."""
    p = B.budget_path(tmp_path / "poster.html")
    B.record_failure(p, "poster.html", 5, NOW + dt.timedelta(minutes=2))
    count, warn = B.load_count(p, "poster.html", NOW)
    assert count == 5 and warn is None


def test_stale_state_silently_resets(tmp_path: Path) -> None:
    """A file older than STALE_AFTER_HOURS is a previous working
    session -- reset without a warning (it's the expected lifecycle,
    not corruption)."""
    p = B.budget_path(tmp_path / "poster.html")
    old = NOW - dt.timedelta(hours=B.STALE_AFTER_HOURS + 1)
    B.record_failure(p, "poster.html", 29, old)
    count, warn = B.load_count(p, "poster.html", NOW)
    assert count == 0 and warn is None


def test_just_inside_stale_window_kept(tmp_path: Path) -> None:
    p = B.budget_path(tmp_path / "poster.html")
    recent = NOW - dt.timedelta(hours=B.STALE_AFTER_HOURS - 1)
    B.record_failure(p, "poster.html", 12, recent)
    count, warn = B.load_count(p, "poster.html", NOW)
    assert count == 12 and warn is None


def test_write_failure_warns_not_raises(tmp_path: Path) -> None:
    """Unwritable destination -> warning string, no exception. The
    geometry verdict must never depend on state-file writability."""
    missing_dir = tmp_path / "not-there" / "x.json"
    warn = B.record_failure(missing_dir, "poster.html", 1, NOW)
    assert warn is not None


def _deny_unlink(monkeypatch, target: Path) -> None:
    """Make ``Path.unlink`` fail for ``target`` only (root ignores
    file-permission tricks, so simulate the I/O failure directly)."""
    real_unlink = Path.unlink

    def deny(self: Path, *a, **kw):
        if self == target:
            raise PermissionError("simulated: locked state file")
        return real_unlink(self, *a, **kw)

    monkeypatch.setattr(Path, "unlink", deny)


def test_clear_zeroes_in_place_when_unlink_fails(
    tmp_path: Path, monkeypatch
) -> None:
    """PASS must never leave a stale count behind: when the file can't
    be removed, clear() falls back to atomically writing count=0 --
    otherwise the next run inherits failures a PASS already forgave,
    breaking the CONSECUTIVE-failures contract."""
    p = B.budget_path(tmp_path / "poster.html")
    B.record_failure(p, "poster.html", 5, NOW)
    _deny_unlink(monkeypatch, p)
    assert B.clear(p, "poster.html", NOW) is None
    count, warn = B.load_count(p, "poster.html", NOW)
    assert count == 0 and warn is None


def test_clear_warns_when_zero_write_also_fails(
    tmp_path: Path, monkeypatch
) -> None:
    p = B.budget_path(tmp_path / "poster.html")
    B.record_failure(p, "poster.html", 5, NOW)
    _deny_unlink(monkeypatch, p)
    monkeypatch.setattr(
        B, "record_failure", lambda *a, **kw: "simulated write failure"
    )
    warn = B.clear(p, "poster.html", NOW)
    assert warn is not None
    # BOTH causes must be diagnosable from the one warning.
    assert "locked state file" in warn
    assert "simulated write failure" in warn


def test_clear_without_poster_name_warns_on_unlink_failure(
    tmp_path: Path, monkeypatch
) -> None:
    """No poster identity -> no zero-write fallback possible; the
    failure must surface as a warning, not silence."""
    p = B.budget_path(tmp_path / "poster.html")
    B.record_failure(p, "poster.html", 5, NOW)
    _deny_unlink(monkeypatch, p)
    assert B.clear(p) is not None


def test_naive_timestamp_treated_as_utc(tmp_path: Path) -> None:
    """A hand-edited state file without tzinfo must not crash the
    comparison logic."""
    p = B.budget_path(tmp_path / "poster.html")
    p.write_text(json.dumps({
        "schema_version": 1, "poster": "poster.html", "count": 4,
        "updated": NOW.replace(tzinfo=None).isoformat(),
    }), encoding="utf-8")
    count, warn = B.load_count(p, "poster.html", NOW)
    assert count == 4 and warn is None
