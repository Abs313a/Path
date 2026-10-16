# SPDX-License-Identifier: MIT

import pytest

from harness.artifacts import ArtifactCollector
from harness.modes import ALL_MODES


@pytest.mark.parametrize("mode", ALL_MODES)
@pytest.mark.parametrize("destination", ["Home", "Trash"])
def test_sidebar_destinations_accept_three_files(pathfm, mode, destination):
    names = [f"drop-{letter}.txt" for letter in "abc"]
    for name in names:
        pathfm.fixture.path(name).write_text(name)
        pathfm.entry(name)
    pathfm.select_entry(names[0])
    for name in names[1:]:
        pathfm.pointer.click(pathfm.entry(name), modifiers=["ctrl"])
    pathfm.wait_for_selection(names)
    target = pathfm.sidebar_button(destination)
    source = pathfm.entry(names[0])
    pathfm.pointer.drag_points(
        pathfm.pointer.drag_origin(source), target.screen_bounds().center, release=False
    )
    try:
        artifacts = ArtifactCollector(test_name=f"sidebar-drop-{destination}-{mode}")
        pathfm.screenshot(artifacts.directory / "hover.png")
    finally:
        pathfm.pointer.connection.button(1, False)
    pathfm.wait(
        lambda: all(not pathfm.fixture.path(name).exists() for name in names),
        "all three sources to leave their original directory",
    )
    directory = pathfm.environment.home if destination == "Home" else pathfm.environment.trash_files
    pathfm.wait(
        lambda: all((directory / name).exists() and (directory / name).read_text() == name for name in names),
        "all three files to arrive intact",
    )
    if destination == "Trash":
        pathfm.keyboard.press("ctrl+z")
        pathfm.wait(
            lambda: all(pathfm.fixture.path(name).exists() for name in names),
            "all three trashed files to be restored by undo",
        )
