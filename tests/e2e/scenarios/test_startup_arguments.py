# SPDX-License-Identifier: MIT
"""Shell arguments reach every requested location without changing path bytes."""

import os
import subprocess

import pytest

from harness import tree
from harness.process import terminate
from harness.application import binary_path
from harness.environment import process_environment


def launch_argument(pathfm, argument):
    variables = process_environment()
    variables.update(pathfm.environment.variables())
    variables.update(pathfm.display.environment)
    subprocess.run(
        [binary_path(), argument],
        env=variables,
        cwd=pathfm.fixture.root,
        check=True,
        timeout=30,
        capture_output=True,
    )


def unavailable_location_window(pathfm, requested):
    return next(
        (
            window
            for window in pathfm.application.application_node.find_all(
                role="frame", name="Path"
            )
            if any(
                "The requested location is unavailable" in label.name
                and requested in label.name
                for label in window.find_all(role="label")
            )
        ),
        None,
    )


def test_missing_directory_can_be_restored_and_retried(pathfm):
    missing = pathfm.fixture.path("requested-missing")
    launch_argument(pathfm, str(missing))

    window = pathfm.wait(
        lambda: unavailable_location_window(pathfm, str(missing)),
        "the unavailable-location error",
    )
    retry = window.find(role="button", name="Retry")
    assert retry is not None

    missing.mkdir()
    (missing / "restored.txt").write_text("restored\n")
    pathfm.pointer.click(retry)
    pathfm.wait(
        lambda: window.find(name="restored.txt") is not None,
        "Retry to open the restored directory",
    )


def test_multiple_arguments_include_non_utf8_directory_and_file(pathfm):
    root = os.fsencode(pathfm.fixture.root)
    directories = [root + b"/startup-first", root + b"/startup-\xff"]
    markers = ["first-argument.txt", "non-utf8-argument.txt"]
    for directory, marker in zip(directories, markers):
        os.mkdir(directory)
        with open(directory + b"/" + marker.encode(), "wb") as stream:
            stream.write(b"startup regression\n")

    file_argument = root + b"/reveal-me.txt"
    with open(file_argument, "wb") as stream:
        stream.write(b"reveal regression\n")
    broken_link = root + b"/broken-link.txt"
    os.symlink(root + b"/missing-target.txt", broken_link)
    colliding_argument = root + b"/collide-\xe9.txt"
    for colliding in (root + b"/collide-\xe8.txt", colliding_argument):
        with open(colliding, "wb") as stream:
            stream.write(b"colliding name\n")

    variables = process_environment()
    variables.update(pathfm.environment.variables())
    variables.update(pathfm.display.environment)
    subprocess.run(
        [
            os.fsencode(binary_path()),
            *directories,
            file_argument,
            broken_link,
            colliding_argument,
        ],
        env=variables,
        cwd=pathfm.fixture.root,
        check=True,
        timeout=30,
        capture_output=True,
    )

    def colliding_selections(windows):
        return [
            sum(node.has_state("selected") for node in window.find_all(name="collide-\ufffd.txt"))
            for window in windows
        ]

    def requested_windows_exist():
        windows = pathfm.application.application_node.find_all(role="frame", name="Path")
        if len(windows) != 6:
            return False
        return 1 in colliding_selections(windows) and all(
            any(window.find(name=marker) is not None for window in windows)
            for marker in markers
        ) and all(
            any(
                node.has_state("selected")
                for window in windows
                for node in window.find_all(name=name)
            )
            for name in ["reveal-me.txt", "broken-link.txt"]
        )

    pathfm.wait(
        requested_windows_exist,
        "one window per argument, with the files and broken symlink revealed",
    )
    windows = pathfm.application.application_node.find_all(role="frame", name="Path")
    assert max(colliding_selections(windows)) == 1


@pytest.mark.parametrize("closed_streams", ["stdout", "stderr", "both"])
def test_startup_with_closed_pipes(pathfm, closed_streams):
    target_dir = pathfm.fixture.path("closed-pipe-target")
    target_dir.mkdir()
    (target_dir / "target.txt").write_text("pipe regression\n")

    pathfm.application.stop()
    variables = process_environment()
    variables.update(pathfm.environment.variables())
    variables.update(pathfm.display.environment)
    variables["RUST_LOG"] = "trace"

    process = subprocess.Popen(
        [binary_path(), str(target_dir)],
        env=variables,
        cwd=pathfm.fixture.root,
        start_new_session=True,
        stdout=subprocess.PIPE if closed_streams in ("stdout", "both") else subprocess.DEVNULL,
        stderr=subprocess.PIPE if closed_streams in ("stderr", "both") else subprocess.DEVNULL,
    )
    try:
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                stream.close()

        def target_window_exists():
            assert process.poll() is None, f"Path exited during startup: {process.returncode}"
            application = tree.find_application("io.github.christitustech.Path")
            if application is None:
                return False
            windows = application.find_all(role="frame", name="Path")
            return any(window.find(name="target.txt") is not None for window in windows)

        pathfm.wait(target_window_exists, "primary startup with closed output pipes")
    finally:
        terminate(process)
