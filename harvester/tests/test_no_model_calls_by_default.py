"""A test never spends unasked (seldon AD-036-R9): the default suite makes zero `claude` calls.

How: a directory holding an executable named `claude` goes first on PATH, and `SELDON_MODELS_HOME`
points at a fixture models home whose lock `cli.path` is that same executable. The harvester's
launchers exec the lock's CLI (harvester.model_launch) and anything else would find `claude` on
PATH, so either route lands on the shim. The shim appends one line per invocation to a record
file and exits 1, so it never answers and never spends.

`test_default_suite_makes_zero_claude_calls` runs the WHOLE test suite (every file under tests/
except this one, which is excluded so the run does not recurse) in a pytest subprocess with
`LIVE_MODEL_CALLS` removed from its environment, and asserts the record is empty. Tests that use
the `seldon_models_home` fixture point `SELDON_MODELS_HOME` at their own fake CLI, which is a fake
by design; this test catches what reaches a launcher without one.

`test_shim_and_gate_catch_a_planted_call` is the positive control (kg_construction_methodology
section 7.6: a verdict is not cited until its instrument has been positive-controlled). It runs,
through the same harness, a planted file holding one ungated launcher call and one
`@pytest.mark.live_model` call, and asserts the shim recorded exactly one invocation and the gate
skipped the other with a reason naming `LIVE_MODEL_CALLS`.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

from tests.conftest import LIVE_MODEL_CALLS_ENV, write_models_home

HARVESTER_ROOT = Path(__file__).resolve().parent.parent
THIS_FILE = Path(__file__).resolve()

#: Wall-clock bound for the nested suite. The whole suite ran in about 35 s on 2026-10-09; this is
#: generous headroom so a slow DB does not fail the test, while a hung run still ends.
NESTED_SUITE_TIMEOUT_S = 900

#: One fixed line per invocation (argv holds the multi-line prompt, so it is not written). The
#: argument count tells a reader which kind of call it was.
_SHIM = """#!/bin/sh
printf 'claude invoked, argc=%s\\n' "$#" >> {record}
exit 1
"""

_PLANTED = '''
from datetime import date
from pathlib import Path

import pytest

from harvester.triage.llm_triage import LlmTriage
from harvester.types import ParsedDoc

AXES = Path({axes!r})


def _score():
    LlmTriage(role="triage", axes_yaml=AXES).score(ParsedDoc(
        title="t", source_url="https://example.com/p", published_date=date(2026, 10, 9),
        rows=[], metadata={{"abstract": "a"}}))


def test_planted_ungated_call():
    """Reaches the real launcher with no fake: the shim must record it."""
    _score()


@pytest.mark.live_model
def test_planted_gated_call():
    """The same call behind the gate: skipped by default, so the shim records nothing."""
    _score()
'''


def _shim_env(tmp_path: Path) -> tuple[dict[str, str], Path]:
    """The environment the nested run gets, and the shim's record file."""
    shim_dir = tmp_path / "shim_bin"
    shim_dir.mkdir()
    record = tmp_path / "claude_invocations.log"
    shim = shim_dir / "claude"
    shim.write_text(_SHIM.format(record=shlex.quote(str(record))))
    shim.chmod(0o755)
    home = tmp_path / "seldon_models"
    write_models_home(home, shim)

    env = dict(os.environ)
    env.pop(LIVE_MODEL_CALLS_ENV, None)
    env["PATH"] = f"{shim_dir}{os.pathsep}{env.get('PATH', '')}"
    env["SELDON_MODELS_HOME"] = str(home)
    return env, record


def _invocations(record: Path) -> list[str]:
    return record.read_text().splitlines() if record.exists() else []


def _pytest(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:randomly", "-p", "no:cacheprovider",
         "-q", "-rs", *args],
        cwd=HARVESTER_ROOT, env=env, capture_output=True, text=True,
        timeout=NESTED_SUITE_TIMEOUT_S)


def test_default_suite_makes_zero_claude_calls(tmp_path):
    env, record = _shim_env(tmp_path)
    proc = _pytest([f"--ignore={THIS_FILE}", "tests"], env)
    tail = proc.stdout[-3000:]
    # 0 = all passed, 1 = some test failed. Anything else (interrupted, internal error, usage
    # error, nothing collected) means the suite did not run, and an empty record would prove
    # nothing.
    assert proc.returncode in (0, 1), f"nested suite did not run (rc {proc.returncode}):\n{tail}"
    assert " passed" in proc.stdout, f"nested suite reports no passed tests:\n{tail}"
    calls = _invocations(record)
    assert calls == [], (
        f"the default suite invoked `claude` {len(calls)} time(s) without "
        f"{LIVE_MODEL_CALLS_ENV}=1 (seldon AD-036-R9); gate the test with "
        f"@pytest.mark.live_model or give it a fake. Invocations: {calls}")


def test_shim_and_gate_catch_a_planted_call(tmp_path):
    env, record = _shim_env(tmp_path)
    planted = tmp_path / "planted" / "test_planted.py"
    planted.parent.mkdir()
    planted.write_text(_PLANTED.format(
        axes=str(HARVESTER_ROOT / "harvester" / "triage" / "research_axes.yaml")))

    # `-p tests.conftest` loads this suite's gate for a file outside tests/.
    proc = _pytest(["-p", "tests.conftest", f"--rootdir={planted.parent}", str(planted)], env)

    assert len(_invocations(record)) == 1, (
        f"the shim must record the one ungated call:\n{proc.stdout[-3000:]}")
    assert "1 skipped" in proc.stdout, proc.stdout[-3000:]
    assert f"{LIVE_MODEL_CALLS_ENV}=1" in proc.stdout, proc.stdout[-3000:]
