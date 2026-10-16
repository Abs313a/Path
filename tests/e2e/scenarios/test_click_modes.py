# SPDX-License-Identifier: MIT
"""Single-click and double-click activation, and switching between them."""

from __future__ import annotations

import time

import pytest
from gi.repository import Atspi

from harness.interaction import SEPARATE_CLICK_GAP
from harness.modes import ALL_MODES

SINGLE_CLICK = pytest.mark.preferences(
    list_folder_clicks=1, list_file_clicks=1,
    grid_folder_clicks=1, grid_file_clicks=1,
    explorer_folder_clicks=1, explorer_file_clicks=1,
)
DOUBLE_CLICK = pytest.mark.preferences(
    list_folder_clicks=2, list_file_clicks=2,
    grid_folder_clicks=2, grid_file_clicks=2,
    explorer_folder_clicks=2, explorer_file_clicks=2,
)


@SINGLE_CLICK
@pytest.mark.parametrize("mode", ALL_MODES)
@pytest.mark.parametrize("initial", ["none", "group"])
def test_single_click_opens_a_directory(pathfm, mode, initial):
    root = pathfm.fixture.root.name
    if initial == "group":
        # A plain press on a member keeps the group for a drag; the release must still open it.
        pathfm.wait_for_selection(["archive"], root)
        pathfm.click_entry_with("todo.txt", ["ctrl"], root)
        pathfm.click_entry_with("documents", ["ctrl"], root)
        pathfm.wait_for_selection(["archive", "documents", "todo.txt"], root)
        time.sleep(SEPARATE_CLICK_GAP)

    pathfm.pointer.click(pathfm.entry("documents", root))

    pathfm.wait(
        lambda: pathfm.pane().name == "documents",
        "one click to open the directory in single-click mode",
    )
    pathfm.entry("notes.txt")
    pathfm.wait_for_selection([], "documents")
    if initial == "group" and mode == "Columns":
        pathfm.wait_for_selection(["documents"], root)


@SINGLE_CLICK
@pytest.mark.preferences(browser_mode="columns", single_click_previews=False)
@pytest.mark.parametrize("reveal_during_press", [False, True])
def test_single_click_opens_a_folder_in_a_clipped_parent_column(
    pathfm, unreserved_columns, reveal_during_press,
):
    browser_left = pathfm.pane().screen_bounds().x
    pathfm.fixture.populate({
        "documents": {"Level 2": {"Level 3": {"old-branch.txt": "old branch\n"}}},
    })
    for name in ["documents", "Level 2", "Level 3"]:
        pathfm.select_entry_with_keyboard(name)
        pathfm.keyboard.press("Return")
        pathfm.wait_for_directory(name)

    folder = pathfm.entry("pictures", directory=pathfm.fixture.root.name)
    bounds = folder.screen_bounds()
    press_x, press_y = max(bounds.x, browser_left) + 12, bounds.center[1]
    pathfm.pointer.move_to(press_x, press_y)
    pathfm.pointer.connection.button(1, True)
    try:
        if reveal_during_press:
            # Move the camera without a wheel gesture, which legitimately
            # cancels the pending click on some GTK versions.
            scrollbar = next(
                node for _, node in pathfm.window.walk()
                if node.role == "scroll bar" and node.has_state("horizontal")
            )
            value = Atspi.Accessible.get_value_iface(scrollbar.accessible)
            assert Atspi.Value.set_current_value(value, 0.0)
        time.sleep(0.2)
        # Sub-threshold pointer jitter must not turn column scrolling into a drag.
        pathfm.pointer.move_to(press_x + 2, press_y)
    finally:
        pathfm.pointer.connection.button(1, False)

    pathfm.wait_for_directory("pictures")
    pathfm.entry("diagram.txt", directory="pictures")
    pathfm.wait_for_selection([], "pictures")


@SINGLE_CLICK
@pytest.mark.parametrize("mode", ALL_MODES)
def test_keyboard_open_selects_the_first_child(pathfm, mode):
    pathfm.select_entry_with_keyboard("documents")
    pathfm.keyboard.press("Return")
    pathfm.wait_for_directory("documents")
    pathfm.wait_for_selection(["notes.txt"], "documents")


@SINGLE_CLICK
@pytest.mark.parametrize("activation", ["mouse", "keyboard"])
def test_sidebar_selection_depends_on_activation(pathfm, activation):
    home = pathfm.environment.home
    (home / "child").mkdir()
    if activation == "mouse":
        pathfm.pointer.click(pathfm.sidebar_button("Home"))
    else:
        pathfm.keyboard.press("Home")
        pathfm.keyboard.press("Left")
        pathfm.wait(
            lambda: pathfm.sidebar_button("Home").has_state("focused"),
            "keyboard focus on the Home sidebar button",
        )
        pathfm.keyboard.press("Return")
    pathfm.wait_for_directory(home.name)
    pathfm.entry("child", home.name)
    pathfm.wait_for_selection(["child"] if activation == "keyboard" else [], home.name)


@SINGLE_CLICK
@pytest.mark.parametrize("mode", ALL_MODES)
def test_keyboard_selection_still_works_in_single_click_mode(pathfm, mode):
    pathfm.keyboard.press("Down")
    pathfm.wait(lambda: pathfm.focused_name() is not None, "keyboard focus")
    focused = pathfm.focused_name()

    root = pathfm.fixture.root.name
    pathfm.wait(
        lambda: pathfm.selected_names(root) == [focused],
        "the keyboard to select without opening anything",
    )
    assert pathfm.current_directory() == root, (
        "moving the keyboard cursor must not navigate in single-click mode"
    )


@DOUBLE_CLICK
@pytest.mark.parametrize("mode", ALL_MODES)
def test_one_click_only_selects_in_double_click_mode(pathfm, mode):
    root = pathfm.fixture.root.name

    pathfm.pointer.click(pathfm.entry("documents"))

    pathfm.wait(
        lambda: pathfm.selected_names() == ["documents"],
        "one click to select in double-click mode",
    )
    assert pathfm.pane().name == root, "one click must not open the directory"


@DOUBLE_CLICK
@pytest.mark.parametrize("mode", ALL_MODES)
def test_two_clicks_open_in_double_click_mode(pathfm, mode):
    pathfm.pointer.double_click(pathfm.entry("documents"))

    pathfm.wait(
        lambda: pathfm.pane().name == "documents",
        "two clicks to open the directory",
    )
    pathfm.entry("notes.txt")
    pathfm.wait_for_selection([], "documents")


@DOUBLE_CLICK
@pytest.mark.parametrize("mode", ALL_MODES)
def test_two_slow_clicks_do_not_open(pathfm, mode):
    """Two clicks outside the double-click interval are two single clicks."""

    root = pathfm.fixture.root.name

    pathfm.pointer.click_twice_slowly(pathfm.entry("documents"))

    pathfm.wait(
        lambda: pathfm.selected_names() == ["documents"],
        "the entry to stay selected",
    )
    assert pathfm.pane().name == root


@DOUBLE_CLICK
@pytest.mark.parametrize("mode", ALL_MODES)
def test_click_then_double_click_opens_without_renaming(pathfm, mode):
    pathfm.pointer.click(pathfm.entry("documents"))
    pathfm.wait(
        lambda: pathfm.selected_names() == ["documents"],
        "the first click to select the folder",
    )
    # Outlast GTK's double-click interval so the pair is a fresh sequence.
    time.sleep(0.6)

    pathfm.pointer.double_click(pathfm.entry("documents"))

    pathfm.wait(
        lambda: pathfm.pane().name == "documents",
        "the double-click to open the folder",
    )
    time.sleep(0.6)
    assert pathfm.window.find(role="text", name="Rename", states={"editable"}) is None, (
        "a double-click must not leave a rename editor behind"
    )


def wait_for_focused_pane(pathfm, name: str) -> None:
    pathfm.wait(
        lambda: (pane := pathfm.focused_pane()) is not None and pane.name == name,
        f"the {name!r} column to take focus",
    )


@pytest.mark.preferences(browser_mode="columns")
@pytest.mark.parametrize("folder_clicks", [
    pytest.param(1, marks=pytest.mark.preferences(list_folder_clicks=1), id="single-click-folders"),
    pytest.param(2, marks=pytest.mark.preferences(list_folder_clicks=2), id="double-click-folders"),
])
@pytest.mark.parametrize("from_parent_column", [False, True], ids=["root", "clipped-parent"])
def test_double_click_leaves_the_folder_open_and_focused(
    pathfm, request, folder_clicks, from_parent_column,
):
    """A double-click ends where a single-click open does, even when its first press scrolls the strip."""

    root = pathfm.fixture.root.name
    browser_left = pathfm.pane().screen_bounds().x
    if from_parent_column:
        # Without the reserved slot the root column is the clipped one.
        request.getfixturevalue("unreserved_columns")
        pathfm.fixture.populate({"documents": {"Level 2": {"Level 3": {"leaf.txt": "leaf\n"}}}})
        for name in ["documents", "Level 2", "Level 3"]:
            pathfm.select_entry_with_keyboard(name)
            pathfm.keyboard.press("Return")
            pathfm.wait_for_directory(name)

    folder = pathfm.settle(pathfm.entry("pictures", directory=root))
    bounds = folder.screen_bounds()
    pathfm.pointer.double_click(
        folder, at=(max(bounds.x, browser_left) + 12, bounds.center[1]),
    )

    wait_for_focused_pane(pathfm, "pictures")
    pathfm.wait_for_selection([], "pictures")
    # Outlast the double-click interval so a late second activation would show.
    time.sleep(0.6)
    assert pathfm.pane_names()[-1] == "pictures"
    wait_for_focused_pane(pathfm, "pictures")


@pytest.mark.preferences(browser_mode="columns", list_folder_clicks=1)
@pytest.mark.parametrize("clicks", [1, 2], ids=["click-row-space", "double-click-name"])
def test_clicking_an_open_folder_focuses_its_column(pathfm, clicks):
    root = pathfm.fixture.root.name
    pathfm.pointer.click(pathfm.entry("documents"))
    pathfm.wait_for_directory("documents")
    pathfm.keyboard.press("Left")
    wait_for_focused_pane(pathfm, root)
    time.sleep(0.6)

    entry = pathfm.entry("documents", root)
    if clicks == 1:
        point = pathfm.pointer.row_whitespace_point(entry, "documents")
        pathfm.pointer.click(entry, at=point)
    else:
        label = entry.find(role="label", name="documents")
        assert label is not None
        point = label.screen_bounds().x + 4, label.screen_bounds().center[1]
        pathfm.pointer.double_click(entry, at=point)

    wait_for_focused_pane(pathfm, "documents")
    time.sleep(0.6)
    assert pathfm.pane_names()[-2:] == [root, "documents"], "the folder must stay open"
    assert pathfm.window.find(role="text", name="Rename", states={"editable"}) is None


@DOUBLE_CLICK
@pytest.mark.preferences(browser_mode="list")
def test_changing_the_preference_takes_effect_without_restarting(pathfm):
    root = pathfm.fixture.root.name
    pathfm.pointer.click(pathfm.entry("documents"))
    pathfm.wait(
        lambda: pathfm.selected_names() == ["documents"],
        "double-click mode to only select",
    )
    assert pathfm.pane().name == root

    _choose_single_click(pathfm)

    pathfm.pointer.click(pathfm.entry("pictures"))
    pathfm.wait(
        lambda: pathfm.pane().name == "pictures",
        "the new preference to apply to the running window",
    )


def _choose_single_click(pathfm) -> None:
    """Switch the List view to single-click activation through Settings."""

    pathfm.pointer.click(pathfm.header_button("Settings"))
    option = pathfm.wait(
        lambda: pathfm.window.find(
            role="toggle button", name="List view Folders Single", rendered=False
        ),
        "the List single-click option in Settings",
    )
    assert option.activate(), "the option should expose an accessible action"
    pathfm.wait(
        lambda: pathfm.environment.read_preferences().get("explorer_folder_clicks")
        == "1",
        "the single-click choice to be saved",
    )
    pathfm.keyboard.press("Escape")
    pathfm.wait(
        lambda: pathfm.window.find(
            role="toggle button", name="List view Folders Single"
        )
        is None,
        "Settings to close",
    )
