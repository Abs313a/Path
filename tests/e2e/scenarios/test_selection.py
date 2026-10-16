# SPDX-License-Identifier: MIT
"""Range selection, toggle selection, and right-click selection behavior."""

from __future__ import annotations

import pytest

from harness.modes import ALL_MODES

ROW_MODES = [mode for mode in ALL_MODES if mode.id != "icons"]


def _name_label_point(entry, *, leftover: bool) -> tuple[int, int]:
    label = entry.find(role="label", name=entry.name)
    assert label is not None
    bounds = label.screen_bounds()
    x = bounds.x + bounds.width - 2 if leftover else bounds.x + 4
    return (x, bounds.center[1])


@pytest.fixture
def root(pathfm) -> str:
    """The fixture directory, named explicitly.

    Columns opens a folder on the click that selects it, so assertions name
    the pane they are about rather than relying on the deepest one.
    """

    return pathfm.fixture.root.name


# Listing-selected origin is the same contract at startup and after keyboard
# entry. Row-space is a separate hit geometry, not a second origin.
SHIFT_RANGE_CASES = [
    pytest.param("startup", "content", id="startup-content"),
    pytest.param("keyboard-entry", "content", id="keyboard-entry-content"),
    pytest.param("keyboard-entry", "row-space", id="keyboard-entry-row-space"),
]


@pytest.mark.parametrize("mode", ALL_MODES)
@pytest.mark.parametrize("arrival,target", SHIFT_RANGE_CASES)
def test_shift_click_ranges_from_the_listing_selected_entry(
    pathfm, mode, root, arrival, target
):
    if arrival == "startup":
        directory = root
        name = "pictures"
        expected = ["archive", "documents", "pictures"]
    else:
        pathfm.select_entry_with_keyboard("documents")
        pathfm.keyboard.press("Return")
        pathfm.wait_for_directory("documents")
        directory = "documents"
        name = "spreadsheet.csv"
        expected = ["notes.txt", "report.md", "spreadsheet.csv"]

    entry = pathfm.entry(name, directory)
    if target == "row-space":
        if mode == "Icons":
            icon = entry.find(role="image")
            assert icon is not None
            bounds = icon.screen_bounds()
            point = (bounds.x - 6, bounds.center[1])
        else:
            label = entry.find(role="label", name=name)
            assert label is not None
            bounds = label.screen_bounds()
            point = (bounds.x + bounds.width - 2, bounds.center[1])
        pathfm.pointer.click(entry, at=point, modifiers=("shift",))
    else:
        pathfm.click_entry_with(name, ["shift"], directory=directory)

    pathfm.wait_for_selection(expected, directory)


@pytest.mark.parametrize("mode", ALL_MODES)
def test_keyboard_selection_after_sidebar_navigation_initializes_the_range_anchor(pathfm, mode):
    home = pathfm.environment.home
    names = ["a.txt", "b.txt", "c.txt"]
    for name in names:
        (home / name).write_text(name)
    pathfm.pointer.click(pathfm.sidebar_button("Home"))
    pathfm.wait_for_directory(home.name)
    pathfm.keyboard.press("Home")
    pathfm.wait_for_selection(["a.txt"], home.name)
    pathfm.click_entry_with("c.txt", ["shift"], directory=home.name)
    pathfm.wait_for_selection(names, home.name)


@pytest.mark.preferences(
    browser_mode="columns", single_click_previews=False,
    sort_key="modified", sort_direction="descending",
)
@pytest.mark.parametrize("target", ["name", "row-space"])
@pytest.mark.usefixtures("unreserved_columns")
def test_shift_click_revisits_a_file_after_opening_a_folder(pathfm, root, target):
    def click(name, modifiers=()):
        entry = pathfm.entry(name, root)
        label = entry.find(role="label", name=name)
        assert label is not None
        bounds = label.screen_bounds()
        x = bounds.x + 4 if target == "name" else bounds.x + bounds.width - 2
        pathfm.pointer.click(entry, at=(x, bounds.center[1]), modifiers=modifiers)

    click("todo.txt")
    pathfm.wait_for_selection(["todo.txt"], root)
    click("documents")
    pathfm.wait_for_directory("documents")
    pathfm.wait_for_selection([], "documents")
    click("todo.txt", ("shift",))
    if target == "name":
        pathfm.wait_for_focused_entry("todo.txt")
    names = [entry.name for entry in pathfm.entries(root)]
    pathfm.wait_for_selection(names[names.index("documents"):names.index("todo.txt") + 1], root)


@pytest.mark.parametrize("mode", ALL_MODES)
def test_modifier_click_on_a_filename_focuses_the_target(pathfm, mode, root):
    pathfm.select_entry("readme.md", root)
    pathfm.wait_for_focused_entry("readme.md")
    entry = pathfm.entry("todo.txt", root)
    label = entry.find(role="label", name="todo.txt")
    assert label is not None
    bounds = label.screen_bounds()
    pathfm.pointer.click(entry, at=(bounds.x + 4, bounds.center[1]), modifiers=("ctrl",))
    pathfm.wait_for_focused_entry("todo.txt")
    pathfm.wait_for_selection(["readme.md", "todo.txt"], root)


@pytest.mark.preferences(browser_mode="columns")
@pytest.mark.usefixtures("unreserved_columns")
def test_returning_to_a_parent_pane_anchors_its_first_entry(pathfm, root):
    pathfm.open_directory("documents", directory=root)
    pathfm.pointer.click(pathfm.pane(root), at=pathfm.background_point(root))
    pathfm.wait_for_selection(["archive"], root)
    pathfm.click_entry_with("pictures", ["shift"], directory=root)
    pathfm.wait_for_selection(["archive", "documents", "pictures"], root)
    assert "documents" not in pathfm.pane_names()


@pytest.mark.parametrize("mode", ALL_MODES)
@pytest.mark.usefixtures("unreserved_columns")
def test_control_click_toggles_individual_entries(pathfm, mode, root):
    pathfm.select_entry("archive", directory=root)

    pathfm.click_entry_with("pictures", ["ctrl"], directory=root)
    pathfm.wait(
        lambda: pathfm.selected_names(root) == ["archive", "pictures"],
        "a control-click to add one entry",
    )

    pathfm.click_entry_with("archive", ["ctrl"], directory=root)
    pathfm.wait(
        lambda: pathfm.selected_names(root) == ["pictures"],
        "a second control-click to remove that entry again",
    )


@pytest.mark.parametrize("mode", ALL_MODES)
@pytest.mark.parametrize("target,previous", [("todo.txt", "readme.md"), ("documents", "archive")])
def test_right_click_selects_the_entry_under_the_pointer(pathfm, mode, root, target, previous):
    pathfm.select_entry("readme.md", directory=root)
    pathfm.wait_for_focused_entry("readme.md")

    pathfm.open_context_menu(target, directory=root)

    pathfm.wait_for_selection([target], root)
    pathfm.dismiss_menu()
    pathfm.wait_for_focused_entry(target)
    assert pathfm.pane_names() == [root], "a folder context menu must not navigate"
    pathfm.keyboard.press("Left" if mode == "Icons" else "Up")
    pathfm.wait_for_focused_entry(previous)
    pathfm.wait_for_selection([previous], root)


@pytest.mark.parametrize("mode", ALL_MODES)
def test_right_click_keeps_an_existing_multi_selection(pathfm, mode, root):
    pathfm.select_entry("todo.txt", directory=root)
    entry = pathfm.entry("readme.md", root)
    pathfm.pointer.click(entry, at=_name_label_point(entry, leftover=False), modifiers=("ctrl",))
    pathfm.wait(
        lambda: pathfm.selected_names(root) == ["readme.md", "todo.txt"],
        "both files to be selected",
    )
    pathfm.wait_for_focused_entry("readme.md")

    pathfm.open_context_menu("todo.txt", directory=root)

    assert pathfm.selected_names(root) == ["readme.md", "todo.txt"], (
        "right-clicking inside a multi-selection must not collapse it"
    )
    pathfm.dismiss_menu()
    pathfm.wait_for_focused_entry("todo.txt")
    pathfm.wait_for_selection(["readme.md", "todo.txt"], root)


@pytest.mark.parametrize("mode", ALL_MODES)
def test_selecting_a_second_entry_replaces_the_first(pathfm, mode, root):
    pathfm.select_entry("readme.md", directory=root)

    pathfm.select_entry("todo.txt", directory=root)

    pathfm.wait(
        lambda: pathfm.selected_names(root) == ["todo.txt"],
        "a plain click to replace the selection",
    )


def _leftover_click_cases():
    # Shift leftover-mouseup × {content, row-space} × ROW_MODES; Ctrl leftover
    # × Columns; unmodified leftover × ROW_MODES. Do not cartesian-explode.
    cases = []
    for mode in ROW_MODES:
        for target in ("content", "row-space"):
            cases.append(
                pytest.param(
                    "shift",
                    target,
                    marks=mode.marks,
                    id=f"shift-{target}-{mode.id}",
                )
            )
    columns = next(mode for mode in ROW_MODES if mode.id == "columns")
    cases.append(
        pytest.param(
            "ctrl",
            "row-space",
            marks=columns.marks,
            id="ctrl-row-space-columns",
        )
    )
    for mode in ROW_MODES:
        cases.append(
            pytest.param(
                None,
                "row-space",
                marks=mode.marks,
                id=f"plain-row-space-{mode.id}",
            )
        )
    return cases


@pytest.mark.parametrize("modifier,target", _leftover_click_cases())
def test_leftover_click_honors_the_press_modifiers(pathfm, modifier, target, root):
    pathfm.open_directory("documents", directory=root)
    pathfm.select_entry("notes.txt", directory="documents")
    entry = pathfm.entry("spreadsheet.csv", "documents")
    point = _name_label_point(entry, leftover=(target == "row-space"))
    if modifier is None:
        pathfm.pointer.click(entry, at=point)
        expected = ["spreadsheet.csv"]
    else:
        pathfm.pointer.click_releasing_modifiers_before_up(
            entry, at=point, modifiers=(modifier,)
        )
        if modifier == "shift":
            expected = ["notes.txt", "report.md", "spreadsheet.csv"]
        else:
            expected = ["notes.txt", "spreadsheet.csv"]
    pathfm.wait_for_selection(expected, "documents")


@pytest.mark.parametrize("mode", ALL_MODES)
def test_a_click_after_navigating_re_anchors_the_range(pathfm, mode, root):
    pathfm.open_directory("documents", directory=root)
    pathfm.select_entry("report.md", directory="documents")

    pathfm.click_entry_with("spreadsheet.csv", ["shift"], directory="documents")

    pathfm.wait(
        lambda: pathfm.selected_names("documents") == ["report.md", "spreadsheet.csv"],
        "the range to start at the clicked entry rather than the loaded one",
    )


ROOT_ENTRIES = ["archive", "documents", "pictures", "readme.md", "todo.txt"]
NEXT_ENTRY = {"Columns": "Down", "Icons": "Right", "List": "Down"}


@pytest.mark.preferences(tenxer_mode=True, type_to_search=False, single_click_previews=False)
@pytest.mark.parametrize("mode", ALL_MODES)
@pytest.mark.usefixtures("unreserved_columns")
def test_tenxer_space_toggles_the_cursor_and_keeps_the_fill(pathfm, mode, root):
    if mode == "Columns":
        pathfm.keyboard.press("Home")
        pathfm.wait_for_focused_entry("archive")
        pathfm.keyboard.press("space")
        pathfm.wait_for_selection(["archive"], root)
        pathfm.wait_for_focused_entry("documents")
        pathfm.keyboard.press("Escape")
        pathfm.wait(lambda: pathfm.selected_names(root) == [], "Escape to clear the fill")
    pathfm.keyboard.press("Home")
    pathfm.wait_for_focused_entry("archive")
    hovered = pathfm.entry("todo.txt", root)
    pathfm.pointer.move_to(*hovered.screen_bounds().center)
    pathfm.keyboard.press(NEXT_ENTRY[mode])
    pathfm.wait_for_focused_entry("documents")
    pathfm.keyboard.press("space")
    pathfm.wait_for_selection(["documents"], root)
    assert pathfm.preview() is None
    assert "todo.txt" not in pathfm.selected_names(root)
    pathfm.wait_for_focused_entry("pictures")

    pathfm.keyboard.press("End")
    pathfm.wait_for_focused_entry("todo.txt")
    assert pathfm.selected_names(root) == ["documents"]

    pathfm.keyboard.press("ctrl+a")
    pathfm.wait_for_selection(ROOT_ENTRIES, root)
    assert pathfm.focused_name() == "todo.txt"
    pathfm.keyboard.press("Home")
    pathfm.wait_for_focused_entry("archive")
    assert pathfm.selected_names(root) == ROOT_ENTRIES

    pathfm.keyboard.press("ctrl+r")
    pathfm.wait(lambda: pathfm.selected_names(root) == [], "Ctrl+R to invert a full pane")
    assert pathfm.focused_name() == "archive"
    pathfm.keyboard.press("End")
    pathfm.wait_for_focused_entry("todo.txt")
    assert pathfm.selected_names(root) == []

    pathfm.keyboard.press("ctrl+a")
    pathfm.wait_for_selection(ROOT_ENTRIES, root)
    pathfm.keyboard.press("Home")
    pathfm.wait_for_focused_entry("archive")
    assert pathfm.selected_names(root) == ROOT_ENTRIES
    pathfm.keyboard.press("ctrl+Down")
    pathfm.wait_for_focused_entry("todo.txt")
    assert pathfm.selected_names(root) == ROOT_ENTRIES
    pathfm.keyboard.press("ctrl+Up")
    pathfm.wait_for_focused_entry("archive")
    assert pathfm.selected_names(root) == ROOT_ENTRIES

    if mode == "Icons":
        pathfm.keyboard.press("ctrl+r")
        pathfm.wait(lambda: pathfm.selected_names(root) == [], "Ctrl+R to clear the pane")
        pathfm.keyboard.press("Home")
        pathfm.wait_for_focused_entry("archive")
        pathfm.keyboard.press("space")
        pathfm.wait_for_selection(["archive"], root)
        pathfm.wait_for_focused_entry("documents")
        pathfm.keyboard.press("Right")
        pathfm.wait_for_focused_entry("pictures")
        assert pathfm.selected_names(root) == ["archive"]
        pathfm.keyboard.press("ctrl+a")
        pathfm.keyboard.press("ctrl+r")
        pathfm.wait(lambda: pathfm.selected_names(root) == [], "Ctrl+R to empty the pane")
        pathfm.keyboard.press("Home")
        pathfm.wait_for_focused_entry("archive")
        pathfm.keyboard.press("Right")
        pathfm.wait_for_focused_entry("documents")
        assert pathfm.selected_names(root) == []

    if mode == "Columns":
        pathfm.keyboard.press("ctrl+r")
        pathfm.wait(lambda: pathfm.selected_names(root) == [], "Ctrl+R to clear the pane")
        pathfm.keyboard.press(NEXT_ENTRY[mode])
        pathfm.wait_for_focused_entry("documents")
        pathfm.keyboard.press("i")
        pathfm.wait(lambda: "documents" in pathfm.pane_names(), "the child column to open")
        pathfm.hover_pane("documents")
        pathfm.keyboard.press("ctrl+a")
        pathfm.wait_for_selection(ROOT_ENTRIES, root)
        assert set(pathfm.selected_names("documents")) != {
            "notes.txt",
            "report.md",
            "spreadsheet.csv",
        }

    pathfm.keyboard.press("Home")
    pathfm.wait_for_focused_entry("archive")
    if mode == "Columns":
        pathfm.keyboard.press("i")
        pathfm.wait(lambda: "archive" in pathfm.pane_names(), "the empty column to open")
        pathfm.keyboard.press("l")
    else:
        pathfm.keyboard.press("Return")
    pathfm.wait_for_directory("archive")
    pathfm.keyboard.press("space")
    pathfm.wait(
        lambda: pathfm.window.find(role="label", name="Nothing to select") is not None,
        "Space in an empty folder to say there is nothing to select",
    )
    assert pathfm.selected_names("archive") == []
    assert pathfm.preview() is None
    pathfm.keyboard.press("BackSpace")
    pathfm.wait_for_directory(root)
    pathfm.keyboard.press("ctrl+a")
    pathfm.wait_for_selection(ROOT_ENTRIES, root)
    assert pathfm.window.find(role="label", name="Nothing to select") is None


PREVIOUS_ENTRY = {"Columns": "Up", "Icons": "Left", "List": "Up"}


@pytest.mark.preferences(tenxer_mode=True, type_to_search=False, single_click_previews=False)
@pytest.mark.parametrize("mode", ALL_MODES)
def test_tenxer_visual_ranges_select_unset_and_keep_the_fill(pathfm, mode, root):
    pathfm.keyboard.press("Home")
    pathfm.wait_for_focused_entry("archive")
    pathfm.keyboard.press("space")
    pathfm.wait_for_selection(["archive"], root)
    pathfm.keyboard.press("End")
    pathfm.wait_for_focused_entry("todo.txt")

    pathfm.keyboard.press("v")
    pathfm.wait_for_selection(["archive", "todo.txt"], root)
    pathfm.keyboard.press(PREVIOUS_ENTRY[mode])
    pathfm.keyboard.press(PREVIOUS_ENTRY[mode])
    pathfm.wait_for_focused_entry("pictures")
    pathfm.wait_for_selection(["archive", "pictures", "readme.md", "todo.txt"], root)
    pathfm.keyboard.press("space")
    pathfm.wait_for_selection(["archive", "readme.md", "todo.txt"], root)
    assert pathfm.focused_name() == "pictures"
    assert pathfm.preview() is None

    pathfm.keyboard.press("Escape")
    pathfm.keyboard.press(PREVIOUS_ENTRY[mode])
    pathfm.wait_for_focused_entry("documents")
    assert pathfm.selected_names(root) == ["archive", "readme.md", "todo.txt"]

    pathfm.keyboard.press("V")
    pathfm.keyboard.press(NEXT_ENTRY[mode])
    pathfm.keyboard.press(NEXT_ENTRY[mode])
    pathfm.wait_for_focused_entry("readme.md")
    pathfm.wait_for_selection(["archive", "todo.txt"], root)
    pathfm.keyboard.press("Escape")
    pathfm.keyboard.press(NEXT_ENTRY[mode])
    pathfm.wait_for_focused_entry("todo.txt")
    assert pathfm.selected_names(root) == ["archive", "todo.txt"]
