# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path

import pytest

from harness import environment as harness_environment

LAUNCH_LOG = "terminal-launches.log"

# Hands off to a (pretend) terminal server and exits at once, like the gnome-terminal
# client or `kitty --single-instance`; records cwd and argv so the test can prove the
# launch happened and targeted the right folder.
STUB_LAUNCHER = """#!/bin/sh
printf '%s\\t%s\\n' "$(pwd)" "$*" >> '{log}'
exit 0
"""


@pytest.fixture
def terminal_launcher(request):
    """Script text for a stub `xdg-terminal-exec`; None leaves PATH empty."""
    return getattr(request, "param", None)


@pytest.fixture
def test_environment(terminal_launcher):
    """PATH holds only the optional stub so launcher availability does not depend on the host."""

    environment = harness_environment.TestEnvironment()
    inherited = environment.variables
    launcher_path = environment.root / "launcher-path"
    launcher_path.mkdir()
    if terminal_launcher is not None:
        stub = launcher_path / "xdg-terminal-exec"
        stub.write_text(terminal_launcher.format(log=environment.root / LAUNCH_LOG))
        stub.chmod(0o755)

    def variables():
        return {**inherited(), "PATH": str(launcher_path)}

    environment.variables = variables
    try:
        yield environment
    finally:
        environment.cleanup()


def _launcher_children(parent_pid: int) -> list[tuple[int, str]]:
    """(pid, state) of every `/proc` entry parented by Path whose comm is the stub launcher."""
    children = []
    for stat in Path("/proc").glob("[0-9]*/stat"):
        try:
            text = stat.read_text()
        except OSError:
            continue  # the process vanished between glob and read
        # comm sits in parentheses and may contain spaces; the state and ppid fields follow it.
        head, _, rest = text.rpartition(") ")
        comm = head.split(" (", 1)[1]
        state, ppid = rest.split()[:2]
        if int(ppid) == parent_pid and comm.startswith("xdg-terminal-ex"):
            children.append((int(stat.parent.name), state))
    return children


def test_opening_a_terminal_without_an_emulator_reports_no_terminal_found(pathfm):
    pathfm.keyboard.press("ctrl+alt+t")

    dialog = pathfm.wait_for_dialog()
    assert dialog.name == "Unable to open terminal", (
        f"unexpected dialog {dialog.name!r}"
    )
    assert any(
        "No terminal emulator" in node.name for node in dialog.find_all(role="label")
    ), f"the error should explain that no terminal was found\n{dialog.dump()}"

    pathfm.pointer.click(pathfm.dialog_button("Close"))
    pathfm.wait(lambda: pathfm.dialog() is None, "the dialog to close")


@pytest.mark.parametrize(
    "terminal_launcher", [STUB_LAUNCHER], ids=["stub-launcher"], indirect=True
)
def test_terminal_launchers_are_reaped_after_they_exit(pathfm, test_environment):
    root = pathfm.fixture.root
    log = test_environment.root / LAUNCH_LOG
    pid = pathfm.application.process.popen.pid

    for count in range(1, 4):
        pathfm.keyboard.press("ctrl+alt+t")
        pathfm.wait(
            lambda count=count: log.exists()
            and len(log.read_text().splitlines()) == count,
            f"terminal launch {count} to run the stub launcher",
        )

    # Every launch targets one folder in the fixture.
    launches = [line.split("\t", 1) for line in log.read_text().splitlines()]
    assert len(launches) == 3, launches
    assert all(launch == launches[0] for launch in launches), launches
    cwd, arguments = launches[0]
    assert arguments.startswith("--dir="), launches
    # pwd reports the physical path while --dir is logical, so compare them resolved.
    folder = Path(arguments.removeprefix("--dir=")).resolve()
    assert Path(cwd).resolve() == folder, launches
    assert folder.is_relative_to(Path(root).resolve()), launches
    pathfm.wait(
        lambda: not _launcher_children(pid), "the terminal launchers to be reaped"
    )
    assert pathfm.dialog() is None
