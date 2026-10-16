# SPDX-License-Identifier: GPL-3.0-or-later
"""After compression completes, the new archive is selected and scrolled into view."""

import pytest

from harness import tree
from harness.fixtures import FixtureTree
from harness.modes import ALL_MODES


@pytest.fixture
def fixture_tree():
    files = {f"{index:03}.txt": f"{index}\n" for index in range(200)}
    fixture = FixtureTree.create(
        {"nested": files, "a": {"b": {"c": {"d": files}}}, **files}
    )
    try:
        yield fixture
    finally:
        fixture.cleanup()


def _compress(pathfm, entry_name, archive_name, directory, folder=""):
    for _ in range(3):
        pathfm.open_context_menu(entry_name, directory=directory)
        # Coordinate-free activation: the popover can still be settling when
        # the item is found, and a synthetic click then lands outside it.
        pathfm.menu_item("Compress…").activate()
        pathfm.wait_for_menu_closed()
        field = None
        try:
            field = pathfm.wait(
                lambda: pathfm.window.find(role="text", states={"editable", "focused"}),
                "the compress name field to take focus",
                timeout=5,
            )
        except tree.TreeTimeout:
            pass
        if field is not None:
            pathfm.keyboard.press("ctrl+a")
            pathfm.keyboard.type_text(archive_name)
            pathfm.wait(
                lambda: field.text == archive_name,
                f"{archive_name!r} to reach the name field",
            )
            pathfm.keyboard.press("Return")
            pathfm.wait(lambda: pathfm.dialog() is None, "the dialog to close")
            path = pathfm.fixture.path(folder).joinpath(f"{archive_name}.zip")
            pathfm.wait(lambda: path.exists(), "the archive to be created")
            return
    raise AssertionError("the compress dialog never accepted the archive name")


@pytest.mark.parametrize("mode", ALL_MODES)
def test_archive_far_from_viewport_is_scrolled_into_view(pathfm, mode):
    """A custom archive name that sorts far from the viewport still gets revealed."""
    pathfm.wait_for_view(mode)

    _compress(pathfm, "005.txt", "zzz", None)

    pathfm.wait_for_selection(["zzz.zip"])
    entry = pathfm.entry("zzz.zip")
    pathfm.wait(lambda: pathfm.on_screen(entry), "the distant archive to be on screen")


@pytest.mark.parametrize("mode", ALL_MODES)
def test_compressed_archive_is_revealed(pathfm, mode):
    """The archive lands at the end of the listing and must be scrolled into view."""
    pathfm.wait_for_view(mode)
    pathfm.keyboard.press("End")
    pathfm.wait_for_focused_entry("199.txt")

    _compress(pathfm, "199.txt", "199", None)

    pathfm.wait_for_selection(["199.zip"])
    entry = pathfm.entry("199.zip")
    pathfm.wait(lambda: pathfm.on_screen(entry), "the new archive to be on screen")


def test_columns_reveals_archive_in_active_child_column(pathfm):
    """Columns mode scrolls the archive into view inside the open child column."""
    pathfm.wait_for_view("Columns")
    pathfm.open_directory("nested")
    pathfm.keyboard.press("End")
    pathfm.wait_for_focused_entry("199.txt")

    _compress(pathfm, "199.txt", "199", "nested", folder="nested")

    pathfm.wait_for_selection(["199.zip"], directory="nested")
    entry = pathfm.entry("199.zip", directory="nested")
    pathfm.wait(
        lambda: pathfm.on_screen(entry),
        "the archive to be on screen in the child column",
    )


def test_columns_reveals_archive_in_deeply_nested_column(pathfm):
    """Columns mode scrolls horizontally and vertically to the archive in a deep column."""
    pathfm.wait_for_view("Columns")
    pathfm.open_directory("a")
    pathfm.open_directory("b", directory="a")
    pathfm.open_directory("c", directory="b")
    pathfm.open_directory("d", directory="c")
    pathfm.keyboard.press("End")
    pathfm.wait_for_focused_entry("199.txt")

    _compress(pathfm, "199.txt", "199", "d", folder="a/b/c/d")

    pathfm.wait_for_selection(["199.zip"], directory="d")
    entry = pathfm.entry("199.zip", directory="d")
    pathfm.wait(
        lambda: pathfm.on_screen(entry),
        "the archive to be on screen in the deep column",
    )


def test_columns_reveals_archive_in_parent_column(pathfm):
    """Columns mode scrolls an archive created in a non-active parent column."""
    root = pathfm.fixture.root.name
    pathfm.wait_for_view("Columns")
    pathfm.open_directory("nested")
    pathfm.keyboard.press("Left")
    pathfm.wait_for_focused_entry("nested")

    _compress(pathfm, "005.txt", "199", root)

    pathfm.wait_for_selection(["199.zip"], directory=root)
    entry = pathfm.entry("199.zip", directory=root)
    pathfm.wait(
        lambda: pathfm.on_screen(entry),
        "the archive to be on screen in the parent column",
    )