"""Tests for the CLI's RunResult.status -> exit code mapping.

Previously the harvester CLI always exited 0 regardless of whether the
run completed, was cancelled by the circuit breaker, or crashed. Wrappers
in scripts/jobs/ propagate the exit code, so this caused cancelled runs
to look identical to healthy runs to launchd and the watchdog.

These tests pin the new mapping so future refactors don't silently
undo the fix.
"""

from harvester.cli import _exit_code_for_status


def test_completed_maps_to_zero():
    assert _exit_code_for_status("completed") == 0


def test_cancelled_maps_to_two():
    """Distinct from failed so monitoring can tell circuit-breaker hits apart
    from genuine crashes.
    """
    assert _exit_code_for_status("cancelled") == 2


def test_failed_maps_to_one():
    assert _exit_code_for_status("failed") == 1


def test_unknown_status_treated_as_failed():
    """Defensive: anything we don't recognize defaults to error. Better to
    over-alert than to swallow a status we don't yet understand.
    """
    assert _exit_code_for_status("running") == 1
    assert _exit_code_for_status("") == 1
    assert _exit_code_for_status("something_new") == 1
