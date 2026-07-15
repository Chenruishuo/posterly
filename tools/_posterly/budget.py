"""Measure-loop circuit breaker state.

``measure`` is the driver of the Step 4 edit->measure loop. A runaway
loop (an agent oscillating on the same column for dozens of rounds)
burns a Chromium render per iteration and, worse, keeps an autonomous
session grinding long after a human should have been called. The
breaker counts **consecutive failed measurements** in a small state
file next to the poster HTML; a PASS (or ``--reset-budget``) clears it.
When the count reaches the cap, ``measure`` refuses to keep iterating
and exits ``EXIT_BUDGET_EXHAUSTED`` (3) with a loud banner.

Design notes (mechanism inspired by ResearchStudio's paper2poster
``.fill_budget.json``; implementation is posterly's own -- see
NOTICE.md):

- The counter lives ON DISK so it survives a compacted / restarted
  agent context -- the exact failure mode that lets an in-prompt round
  count silently reset.
- Only *completed* measurements count: a run that never produced
  geometry (Playwright missing, nav timeout, MathJax settle failure)
  is an environment problem, not a loop iteration.
- Consecutive-failure semantics: a poster that reaches PASS and is
  later re-edited starts from a clean budget instead of inheriting
  stale debt.
- A stale state file (older than ``STALE_AFTER_HOURS``) is treated as a
  new working session and reset -- posterly is used interactively
  across days on the same file, unlike the batch pipeline this borrows
  from.
- State I/O must never break the geometry gate: every failure path
  degrades to "budget disabled + warning", never to a crash or a
  spurious gate verdict.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import tempfile
from pathlib import Path

#: Default cap on CONSECUTIVE failed measurements before the breaker
#: trips. A normal posterly session passes through PASS states often
#: (which reset the count); 30 straight failures on one poster is a
#: pathological loop, not diligence.
DEFAULT_MEASURE_BUDGET = 30

#: A state file untouched for this many hours is a previous working
#: session; its count no longer describes the current loop.
STALE_AFTER_HOURS = 12.0

#: Exit code for "budget exhausted" -- distinct from 1 (gate FAIL) and
#: 2 (usage/environment error) so callers can tell "stop iterating"
#: from "fix the poster".
EXIT_BUDGET_EXHAUSTED = 3

_SCHEMA_VERSION = 1


def budget_path(html_path: Path) -> Path:
    """State-file path for one poster:
    ``.<name>.posterly_budget.json``.

    Keyed by the HTML file's FULL name (not stem) so two posters in the
    same directory never share a budget -- including the
    ``poster.html`` / ``poster.htm`` pair a stem key would collide.
    """
    return html_path.parent / f".{html_path.name}.posterly_budget.json"


def _now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def load_count(
    path: Path,
    poster_name: str,
    now: _dt.datetime | None = None,
) -> tuple[int, str | None]:
    """Read the consecutive-failure count. Returns ``(count, warning)``.

    Any unreadable / implausible state degrades to ``(0, warning)``:
    missing file (no warning -- the normal fresh state), corrupt JSON,
    wrong schema, a timestamp in the future (clock skew / copied file),
    or a stale timestamp (previous session; silently resets).
    """
    now = now or _now()
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return 0, None
    except OSError as exc:
        return 0, f"could not read {path.name}: {exc}"
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("not a JSON object")
        count = int(data["count"])
        updated = _dt.datetime.fromisoformat(str(data["updated"]))
        if data.get("schema_version") != _SCHEMA_VERSION:
            raise ValueError("unknown schema_version")
        if count < 0:
            raise ValueError("negative count")
    except (KeyError, ValueError, TypeError) as exc:
        return 0, f"corrupt budget state {path.name} ({exc}); reset to 0"
    stored_poster = data.get("poster")
    if stored_poster is not None and stored_poster != poster_name:
        return 0, (
            f"budget state {path.name} belongs to another poster "
            f"({stored_poster!r}); reset to 0"
        )
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=_dt.timezone.utc)
    if updated > now + _dt.timedelta(minutes=5):
        return 0, (
            f"budget state {path.name} has a future timestamp; reset to 0"
        )
    if (now - updated) > _dt.timedelta(hours=STALE_AFTER_HOURS):
        return 0, None  # previous session -- silent, expected reset
    return count, None


def record_failure(
    path: Path,
    poster_name: str,
    count: int,
    now: _dt.datetime | None = None,
) -> str | None:
    """Atomically persist ``count``. Returns a warning string on I/O
    failure (the caller prints it; the gate verdict is never affected).
    """
    now = now or _now()
    payload = json.dumps({
        "schema_version": _SCHEMA_VERSION,
        "poster": poster_name,
        "count": count,
        "updated": now.replace(microsecond=0).isoformat(),
    })
    try:
        fd, tmp = tempfile.mkstemp(
            prefix=path.name + ".", dir=str(path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except OSError as exc:
        return (
            f"could not write budget state {path.name} ({exc}); "
            "circuit breaker will not persist across runs"
        )
    return None


def clear(
    path: Path,
    poster_name: str | None = None,
    now: _dt.datetime | None = None,
) -> str | None:
    """Remove the state file (PASS or ``--reset-budget``).

    When the file exists but cannot be removed, falls back to
    atomically overwriting it with ``count = 0`` (needs
    ``poster_name``) -- a stale count surviving a PASS would break the
    CONSECUTIVE-failures contract on the next run. Returns a warning
    string only when the state could be neither removed nor zeroed --
    callers must surface it and must NOT let the stale count produce a
    phantom breaker (e.g. by disabling the budget for the run). A
    missing file is the normal case and returns ``None``.
    """
    try:
        path.unlink()
        return None
    except FileNotFoundError:
        return None
    except OSError as exc:
        zero_warn = None
        if poster_name is not None:
            zero_warn = record_failure(path, poster_name, 0, now)
            if zero_warn is None:
                return None  # zeroed in place -- semantically cleared
        detail = (
            f"; zero-write fallback also failed ({zero_warn})"
            if zero_warn else ""
        )
        return (
            f"could not remove budget state {path.name} ({exc})"
            f"{detail}; the stale failure count may persist"
        )
    return None


def breaker_banner(count: int, cap: int, *, pre_render: bool = False) -> str:
    """The loud stop banner. ``pre_render=True`` = refused before even
    opening the browser (the cap was already reached last run)."""
    when = (
        "Budget was already exhausted -- refusing to render again."
        if pre_render else
        "This measurement exhausted the budget."
    )
    return (
        "=" * 68 + "\n"
        f"  CIRCUIT BREAKER -- {count}/{cap} consecutive failed "
        "measurements.\n"
        f"  {when}\n"
        "  Stop iterating. The loop is not converging: re-think the "
        "layout\n"
        "  (re-pack cards across columns -- see `poster_check.py pack`, "
        "or\n"
        "  reselect the template/canvas) or escalate to the human with "
        "the\n"
        "  current best state rendered.\n"
        "  The counter resets on the first PASS, after "
        f"{STALE_AFTER_HOURS:.0f}h idle, or via\n"
        "  --reset-budget (use it only for a deliberate fresh start, "
        "not to\n"
        "  keep grinding the same edits).\n"
        + "=" * 68
    )
