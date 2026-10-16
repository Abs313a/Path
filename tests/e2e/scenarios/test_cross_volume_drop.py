# SPDX-License-Identifier: MIT
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def drop_volume(pathfm):
    with tempfile.TemporaryDirectory(prefix="pathfm-drop-volume-", dir="/dev/shm") as directory:
        volume = Path(directory)
        assert volume.stat().st_dev != pathfm.fixture.path("todo.txt").stat().st_dev
        pathfm.fixture.path("drop-volume").symlink_to(volume, target_is_directory=True)
        yield volume


@pytest.mark.parametrize("action,tabs", [("Copy", 0), ("Move", 1), ("Cancel", 2)])
@pytest.mark.preferences(cross_volume_drop_strategy="always-ask")
def test_enter_activates_the_focused_cross_volume_choice(pathfm, drop_volume, action, tabs):
    contents = pathfm.fixture.path("todo.txt").read_bytes()
    pathfm.pointer.drag(pathfm.entry("todo.txt"), pathfm.entry("drop-volume"))
    pathfm.wait_for_dialog()
    for _ in range(tabs):
        pathfm.keyboard.press("shift+Tab")
    pathfm.wait(lambda: pathfm.dialog_button(action).has_state("focused"), f"{action} focused")
    pathfm.keyboard.press("Return")
    pathfm.wait(lambda: pathfm.dialog() is None, "the copy-or-move dialog to close")
    source = pathfm.fixture.path("todo.txt")
    destination = drop_volume / "todo.txt"
    if action == "Cancel":
        assert not destination.exists(), "Cancel must not start a transfer"
        assert source.exists()
    else:
        pathfm.wait(lambda: destination.exists(), "the destination to be created")
        if action == "Move":
            pathfm.wait(lambda: not source.exists(), "the source to move")
        else:
            assert source.exists(), "Copy must preserve the source"
        assert destination.read_bytes() == contents


@pytest.mark.preferences(cross_volume_drop_strategy="always-copy")
def test_plain_cross_volume_copy_does_not_prompt_or_remove_source(pathfm, drop_volume):
    source = pathfm.fixture.path("todo.txt")
    contents = source.read_bytes()
    pathfm.pointer.drag(pathfm.entry("todo.txt"), pathfm.entry("drop-volume"))
    destination = drop_volume / "todo.txt"
    pathfm.wait(lambda: destination.exists(), "the cross-device copy")
    assert source.read_bytes() == contents
    assert destination.read_bytes() == contents
    assert pathfm.dialog() is None
