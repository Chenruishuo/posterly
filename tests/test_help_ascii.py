"""`--help` output must be ASCII (round-9): it lands in CI logs and
pasted GitHub issues, where raw Unicode mojibakes on legacy terminals."""
from __future__ import annotations

import argparse

import poster_check
import render_preview


def _all_help(parser: argparse.ArgumentParser) -> str:
    """Top-level help plus every subcommand's help."""
    texts = [parser.format_help()]
    for act in parser._actions:
        if isinstance(act, argparse._SubParsersAction):
            for sub in act.choices.values():
                texts.append(sub.format_help())
    return "\n".join(texts)


def test_poster_check_help_is_ascii() -> None:
    # Raises UnicodeEncodeError (failing the test) on any non-ASCII char.
    _all_help(poster_check.build_parser()).encode("ascii")


def test_render_preview_help_is_ascii() -> None:
    render_preview.build_parser().format_help().encode("ascii")
