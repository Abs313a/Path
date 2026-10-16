# SPDX-License-Identifier: MIT
"""Switching between the Columns, Icons, and List presentations."""

from __future__ import annotations

import math
import time

import pytest
from harness.interaction import SEPARATE_CLICK_GAP

from harness.keyboard_layout import AZERTY, US

MODES = ["Columns", "Icons", "List"]
MODE_SHORTCUTS = {"Columns": "ctrl+1", "Icons": "ctrl+2", "List": "ctrl+3"}
STORED_MODES = {"Columns": '"columns"', "Icons": '"icons"', "List": '"list"'}


@pytest.mark.parametrize("mode", ["Icons", "List"])
def test_appearance_menu_switches_presentation(pathfm, mode):
    assert pathfm.view_mode() == "Columns"
    directory = pathfm.fixture.root.name

    pathfm.switch_view(mode)

    assert pathfm.view_mode() == mode
    assert pathfm.pane().name == directory
    assert "documents" in pathfm.entry_names()
    pathfm.wait(
        lambda: pathfm.environment.read_preferences().get("browser_mode")
        == STORED_MODES[mode],
        "the chosen view to be written to settings.toml",
    )


# AZERTY types & é " on the digit row without Shift; the row still switches views.
@pytest.mark.parametrize("layout", [US, AZERTY], ids=lambda layout: layout.name)
def test_shortcut_round_trip_preserves_selection_and_updates_the_appearance_menu(
    pathfm, keyboard_layout, layout
):
    pathfm.select_entry("todo.txt")
    for mode in ["Icons", "List", "Columns"]:
        with keyboard_layout(layout):
            pathfm.keyboard.press(MODE_SHORTCUTS[mode])
            pathfm.wait_for_view(mode)
        assert pathfm.pane_names()[0] == pathfm.fixture.root.name
        assert "documents" in pathfm.entry_names()
        pathfm.wait(
            lambda: "todo.txt" in pathfm.all_selected_names(),
            f"the selection to survive the switch to {mode}",
        )

        pathfm.open_appearance_menu()
        for candidate in MODES:
            option = pathfm.window.find(role="radio menu item", name=candidate)
            assert option is not None
            assert option.has_state("checked") == (candidate == mode), (mode, candidate)
        grouping = pathfm.window.find(role="check menu item", name="Group by file type")
        assert grouping is not None
        assert ("sensitive" in grouping.states) == (mode == "List")
        pathfm.keyboard.press("Escape")
        pathfm.wait(
            lambda: pathfm.window.find(role="radio menu item", name="Columns") is None,
            "the appearance menu to close",
        )


def test_switching_preserves_directory_selection_and_sort(pathfm):
    pathfm.select_entry("pictures")
    ascending = pathfm.entry_names("pictures")
    assert ascending == ["diagram.txt", "photo.txt"]

    pathfm.pointer.move_to(*pathfm.pane("pictures").screen_bounds().center)
    reverse_sort = pathfm.wait(
        lambda: pathfm.pane("pictures").find(
            role="button", name="Ascending — click to reverse"
        ),
        "the hovered pane's sort action to appear",
    )
    pathfm.pointer.click(reverse_sort)
    pathfm.wait(
        lambda: pathfm.entry_names("pictures") == list(reversed(ascending)),
        "the open pane to sort descending",
    )
    pathfm.select_entry("diagram.txt", directory="pictures")

    pathfm.keyboard.press(MODE_SHORTCUTS["List"])
    pathfm.wait_for_view("List")

    assert pathfm.pane().name == "pictures", (
        "switching should land on the directory the Columns view had open"
    )
    assert pathfm.entry_names() == list(reversed(ascending)), (
        "the descending sort should survive the switch"
    )
    pathfm.wait(
        lambda: pathfm.selected_names() == ["diagram.txt"],
        "the selection to survive the switch",
    )
    pathfm.wait_for_focused_entry("diagram.txt")


@pytest.mark.parametrize("start", ["input", "result"])
def test_switching_preserves_the_pane_filter(pathfm, start):
    pathfm.keyboard.press("ctrl+f")
    field = pathfm.editable_field()
    pathfm.keyboard.type_text("todo")
    pathfm.wait(lambda: field.text == "todo", "the filter query to be typed")
    pathfm.wait(
        lambda: pathfm.matches() == ["todo.txt"],
        "the filter to narrow the listing",
    )
    if start == "result":
        pathfm.keyboard.press("Down")
        pathfm.wait_for_focused_entry("todo.txt")

    for mode in ["Icons", "List", "Columns"]:
        pathfm.keyboard.press(MODE_SHORTCUTS[mode])
        pathfm.wait_for_view(mode)
        pathfm.wait(
            lambda: any(
                node.text == "todo"
                for node in pathfm.window.find_all(role="text", states={"editable"})
            ),
            "the filter query to survive the switch",
        )
        pathfm.wait(
            lambda: pathfm.matches() == ["todo.txt"],
            "the narrowed listing to survive the switch",
        )
        if start == "input":
            field = pathfm.editable_field()
            assert field.text == "todo"
            # Down from the field reaches a result, not the footer.
            pathfm.keyboard.press("Down")
            pathfm.wait_for_focused_entry("todo.txt")
            pathfm.keyboard.press("Up")
            pathfm.editable_field()
        else:
            pathfm.wait_for_focused_entry("todo.txt")


def test_list_column_resize_tracks_the_pointer_without_an_initial_jump(pathfm):
    pathfm.switch_view("List")
    for label in ["Name", "Mode", "Size", "Type", "Modified"]:
        heading = pathfm.wait(
            lambda: pathfm.pane().find(role="button", name=label),
            f"the {label} heading to appear",
        )
        cell = heading.parent
        assert cell is not None
        before = cell.screen_bounds()
        start = (before.x + before.width - 3, before.y + before.height // 2)
        pathfm.pointer.drag_points(start, (start[0] - 12, start[1]))
        pathfm.wait(
            lambda: abs(cell.screen_bounds().width - (before.width - 12)) <= 2,
            f"the {label} column to shrink by the pointer's 12-pixel movement",
        )


STANDARD_COLUMN_WIDTH = 300


def _saved_column_width(pathfm) -> int:
    return int(pathfm.environment.read_preferences().get("browser_column_width", 0))


def test_column_autofit_and_drag_stay_inside_the_browser_area(pathfm):
    long_name = "x" * 216
    pathfm.fixture.path(long_name).write_text("")
    pathfm.entry(long_name)
    pane = pathfm.pane()
    column = pane.screen_bounds()
    middle = column.y + column.height // 2
    window = pathfm.window_bounds()
    # A fresh column has the standard width times the interface scale, and
    # saved widths are unscaled.
    scale = column.width / STANDARD_COLUMN_WIDTH
    # The root column starts at the browser area's left edge; the preview slot
    # yields to a column, so the area runs to the window's right edge.
    area = math.ceil((window.x + window.width - column.x) / scale)

    pathfm.pointer.double_click(pane, at=(column.x + column.width - 3, middle))
    fitted = pathfm.wait(
        lambda: (width := _saved_column_width(pathfm)) > STANDARD_COLUMN_WIDTH and width,
        "autofit to save the fitted width",
    )
    assert fitted <= area, f"autofit saved {fitted}, wider than the browser area ({area} unscaled px)"

    # Narrow the column first so the outward drag has room to save a change.
    time.sleep(SEPARATE_CLICK_GAP)
    edge = pathfm.pane().screen_bounds()
    start = (edge.x + edge.width - 3, middle)
    pathfm.pointer.drag_points(start, (start[0] - 200, middle))
    narrowed = pathfm.wait(
        lambda: (width := _saved_column_width(pathfm)) < fitted and width,
        "the inward drag to save a narrower width",
    )

    time.sleep(SEPARATE_CLICK_GAP)
    edge = pathfm.pane().screen_bounds()
    start = (edge.x + edge.width - 3, middle)
    pathfm.pointer.drag_points(start, (window.x + window.width + 300, middle))
    dragged = pathfm.wait(
        lambda: (width := _saved_column_width(pathfm)) > narrowed and width,
        "the outward drag to save a wider width",
    )
    assert dragged <= area, f"the drag saved {dragged}, wider than the browser area ({area} unscaled px)"


@pytest.mark.preferences(browser_column_width=1729)
def test_an_oversized_saved_column_width_opens_inside_the_window(pathfm):
    pane = pathfm.pane()
    refresh = pathfm.wait(
        lambda: pane.find(role="button", name="Refresh (F5)"),
        "the column's header actions",
    )
    window = pathfm.window_bounds()
    window_right = window.x + window.width
    # Let the startup layout (sidebar budget, preview reservation) settle.
    time.sleep(SEPARATE_CLICK_GAP)
    column = pane.screen_bounds()
    actions = refresh.screen_bounds()
    assert column.x + column.width <= window_right, (
        f"the column's resize edge at {column.x + column.width} is past the window edge {window_right}"
    )
    assert actions.x + actions.width <= window_right, (
        f"the header actions end at {actions.x + actions.width}, past the window edge {window_right}"
    )
