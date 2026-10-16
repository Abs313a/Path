# SPDX-License-Identifier: MIT
"""Keyboard-only movement, activation, and multi-selection."""

from __future__ import annotations

import pytest
from harness.keyboard_layout import RUSSIAN, US
from harness.modes import (
    ALL_MODES,
    COLUMNS_AND_ONE,
    NEXT_ENTRY_KEY,
    PREVIOUS_ENTRY_KEY,
    SINGLE_PANE_MODES,
)

ROOT_ENTRIES = ["archive", "documents", "pictures", "readme.md", "todo.txt"]

# 10xer moves the cursor and keeps the selection. On Russian its j key types о.
ARROW_CASES = [
    pytest.param(
        mode.values[0], bindings, US, "todo.txt", marks=mode.marks, id=f"{bindings}-{mode.id}"
    )
    for bindings in ("arrows", "hjkl")
    for mode in ALL_MODES
] + [
    pytest.param(
        "Columns",
        "hjkl",
        RUSSIAN,
        "readme.md",
        marks=pytest.mark.preferences(browser_mode="columns", tenxer_mode=True),
        id="hjkl-columns-tenxer-ru",
    )
]


@pytest.mark.preferences(type_to_search=False)
@pytest.mark.parametrize("mode, bindings, layout, selected", ARROW_CASES)
def test_arrow_keys_move_focus_and_selection(
    pathfm, keyboard_layout, mode, bindings, layout, selected
):
    assert pathfm.entry_names() == ROOT_ENTRIES

    # A file, so that a single click never navigates in any presentation.
    pathfm.select_entry("readme.md")
    pathfm.wait_for_focused_entry("readme.md")

    aliases = {"Left": "h", "Down": "j", "Up": "k", "Right": "l"}
    next_key = NEXT_ENTRY_KEY[mode]
    previous_key = PREVIOUS_ENTRY_KEY[mode]
    if bindings == "hjkl":
        next_key, previous_key = aliases[next_key], aliases[previous_key]
    with keyboard_layout(layout):
        pathfm.keyboard.press(next_key)
        pathfm.wait_for_focused_entry("todo.txt")
        pathfm.wait(
            lambda: pathfm.selected_names() == [selected],
            f"the selection to be {selected} after the move",
        )

        pathfm.keyboard.press(previous_key)
        pathfm.wait_for_focused_entry("readme.md")


@pytest.mark.preferences(arrow_navigation_scoped=True, type_to_search=False)
@pytest.mark.parametrize("mode", ALL_MODES)
@pytest.mark.parametrize("bindings", ["arrows", "hjkl"])
def test_arrow_scope_keeps_focus_in_files_and_toggles_live(pathfm, mode, bindings):
    up, left = ("Up", "Left") if bindings == "arrows" else ("k", "h")
    pathfm.select_entry("readme.md")
    pathfm.keyboard.press("Home")
    pathfm.wait_for_focused_entry("archive")
    for key in [up, left, up]:
        pathfm.keyboard.press(key)
        pathfm.wait_for_focused_entry("archive")

    pathfm.keyboard.press("ctrl+\\")
    pathfm.wait(
        lambda: pathfm.environment.read_preferences().get("arrow_navigation_scoped") == "false",
        "arrow scope disabled by shortcut",
    )
    pathfm.keyboard.press(up)
    pathfm.wait(lambda: pathfm.focused_name() is None, "Up leaves the file list")
    pathfm.keyboard.press("Down")
    pathfm.wait_for_focused_entry("archive")
    pathfm.keyboard.press("ctrl+\\")
    pathfm.wait(
        lambda: pathfm.environment.read_preferences().get("arrow_navigation_scoped") == "true",
        "arrow scope enabled by shortcut",
    )
    pathfm.keyboard.press(up)
    pathfm.wait_for_focused_entry("archive")


@pytest.mark.preferences(browser_mode="icons", type_to_search=False)
def test_tenxer_icons_stay_on_tiles_at_edges_in_search_and_peek(pathfm):

    pathfm.keyboard.press("ctrl+shift+m")
    pathfm.wait(
        lambda: pathfm.environment.read_preferences().get("tenxer_mode") == "true",
        "10xer mode to turn on",
    )
    root = pathfm.current_directory()
    pathfm.keyboard.press("Home")
    pathfm.wait_for_focused_entry("archive")
    for key in ("Left", "h", "KP_Left"):
        pathfm.keyboard.press(key)
        pathfm.wait_for_focused_entry("archive")
        assert pathfm.current_directory() == root

    empty = pathfm.fixture.path("empty-icons")
    empty.mkdir()
    pathfm.keyboard.press("F5")
    pathfm.select_entry("empty-icons")
    pathfm.keyboard.press("o")
    pathfm.wait_for_directory("empty-icons")
    for key in ("h", "j", "k", "l", "Left", "Down", "i"):
        pathfm.keyboard.press(key)
        assert pathfm.current_directory() == "empty-icons"
        assert pathfm.peek() is None
    pathfm.keyboard.press("BackSpace")
    pathfm.wait_for_directory(root)

    pathfm.select_entry("documents")
    pathfm.keyboard.press("i")
    pathfm.wait(lambda: pathfm.peek() is not None, "i to open the folder peek")
    assert pathfm.current_directory() == root
    assert pathfm.focused_name() == "documents"
    pathfm.keyboard.press("i")
    pathfm.wait(lambda: pathfm.peek() is None, "a second i to close the folder peek")
    pathfm.select_entry("readme.md")
    pathfm.keyboard.press("i")
    pathfm.wait(lambda: pathfm.preview() is not None, "i to open the file preview")
    assert pathfm.peek() is None
    assert pathfm.current_directory() == root
    assert pathfm.focused_name() == "readme.md", "i keeps focus on the tile"
    pathfm.keyboard.press("i")
    pathfm.wait(lambda: pathfm.preview() is None, "a second i to close the preview")
    pathfm.wait_for_focused_entry("readme.md")

    pathfm.keyboard.press("ctrl+shift+m")
    pathfm.wait(
        lambda: pathfm.environment.read_preferences().get("tenxer_mode") == "false",
        "10xer mode to turn off",
    )
    pathfm.keyboard.press("ctrl+f")
    pathfm.editable_field()
    pathfm.keyboard.type_text("txt")
    pathfm.wait(lambda: len(pathfm.matches()) >= 2, "icon search hits")
    pathfm.keyboard.press("Down")
    pathfm.wait(
        lambda: pathfm.focused_name() in pathfm.matches(),
        "Down to focus a search hit",
    )
    pathfm.keyboard.press("ctrl+shift+m")
    pathfm.wait(
        lambda: pathfm.environment.read_preferences().get("tenxer_mode") == "true",
        "10xer mode to turn on over search results",
    )
    before = pathfm.current_directory()
    shown = list(pathfm.matches())
    pathfm.keyboard.press("Down")
    pathfm.keyboard.press("j")
    assert pathfm.current_directory() == before
    assert pathfm.matches() == shown, "directional keys dismissed the search results"
    assert pathfm.focused_name() in shown
    assert pathfm.peek() is None


@pytest.mark.preferences(tenxer_mode=True, type_to_search=False)
def test_tenxer_sidebar_and_header_round_trips(pathfm):

    empty = pathfm.fixture.path("empty-sidebar")
    empty.mkdir()
    # Clicks target rows by position, so the monitor must list the folder first.
    pathfm.entry("empty-sidebar")
    for chord, mode in (("ctrl+1", "Columns"), ("ctrl+3", "List"), ("ctrl+2", "Icons")):
        pathfm.keyboard.press(chord)
        pathfm.wait_for_view(mode)
        root = pathfm.current_directory()
        pathfm.select_entry("readme.md")
        pathfm.wait_for_focused_entry("readme.md")

        toggle = pathfm.window.find(name="Toggle sidebar (Ctrl+N)")
        assert toggle is not None, "sidebar toggle"
        pathfm.keyboard.press("Tab")
        pathfm.wait(lambda: toggle.has_state("focused"), "Tab to focus the sidebar toggle")
        assert pathfm.selected_names() == ["readme.md"]
        pathfm.keyboard.press("h")
        pathfm.wait_for_focused_entry("readme.md")
        assert pathfm.current_directory() == root

        pathfm.keyboard.press("Tab")
        pathfm.wait(lambda: toggle.has_state("focused"), "Tab to return to the sidebar toggle")
        # The toggle steps full -> rail -> hidden; the rail keeps the Home row.
        pathfm.keyboard.press("space")
        pathfm.wait(
            lambda: pathfm.window.find(role="button", name="Home") is not None,
            "Space on the header toggle to compact the sidebar",
        )
        pathfm.keyboard.press("space")
        pathfm.wait(
            lambda: pathfm.window.find(role="button", name="Home") is None,
            "Space again on the header toggle to hide the sidebar",
        )
        pathfm.keyboard.press("ctrl+shift+b")
        assert pathfm.window.find(role="button", name="Home") is None
        assert pathfm.selected_names() == ["readme.md"]
        pathfm.keyboard.press("space")
        pathfm.wait(
            lambda: pathfm.window.find(role="button", name="Home") is not None,
            "Space to show the sidebar again",
        )
        pathfm.keyboard.press("h")
        pathfm.wait_for_focused_entry("readme.md")

        pathfm.keyboard.press("ctrl+shift+b")
        home = pathfm.sidebar_button("Home")
        pathfm.wait(lambda: home.has_state("focused"), "Ctrl+Shift+B to focus the sidebar")
        assert pathfm.selected_names() == ["readme.md"]
        assert pathfm.current_directory() == root
        pathfm.keyboard.press("j")
        pathfm.wait(lambda: not home.has_state("focused"), "j to move to the next place")
        assert pathfm.current_directory() == root
        assert pathfm.selected_names() == ["readme.md"]
        pathfm.keyboard.press("h")
        pathfm.wait_for_focused_entry("readme.md")

        pathfm.keyboard.press("ctrl+shift+b")
        pathfm.wait(lambda: home.has_state("focused"), "the sidebar to take focus again")
        pathfm.keyboard.press("Return")
        pathfm.wait(lambda: pathfm.current_directory() != root, "Enter to open the focused place")
        assert not home.has_state("focused")
        pathfm.keyboard.press("alt+Left")
        pathfm.wait_for_directory(root)

        pathfm.select_entry("empty-sidebar")
        pathfm.keyboard.press("o")
        pathfm.wait_for_directory("empty-sidebar")
        assert pathfm.selected_names() == []
        pathfm.keyboard.press("ctrl+shift+b")
        pathfm.wait(lambda: home.has_state("focused"), "sidebar focus from an empty directory")
        pathfm.keyboard.press("BackSpace")
        pathfm.wait_for_directory("empty-sidebar")
        assert pathfm.selected_names() == []
        pathfm.keyboard.press("BackSpace")
        pathfm.wait_for_directory(root)


@pytest.mark.preferences(tenxer_mode=True, type_to_search=True)
def test_tenxer_keeps_location_edit_and_skips_the_filter_shortcut(pathfm):
    pathfm.select_entry("readme.md")
    names = pathfm.entry_names()

    pathfm.keyboard.press("ctrl+f")
    pathfm.wait(
        lambda: pathfm.window.find(role="text", states={"editable", "focused"}) is None,
        "Ctrl+F does not open a filter while 10xer is on",
    )
    assert pathfm.entry_names() == names
    assert pathfm.environment.read_preferences().get("tenxer_mode") == "true"

    pathfm.keyboard.press("ctrl+l")
    field = pathfm.editable_field()
    pathfm.keyboard.press("q")
    pathfm.wait(lambda: "q" in field.text.lower(), "q is typed into the location field")
    assert pathfm.environment.read_preferences().get("tenxer_mode") == "true"
    assert pathfm.entry_names() == names

@pytest.mark.parametrize("mode", COLUMNS_AND_ONE)
def test_alt_up_and_history_navigate_between_directories(pathfm, mode):
    root = pathfm.fixture.root.name

    pathfm.open_directory("documents")
    pathfm.keyboard.press("alt+Up")
    pathfm.wait_for_directory(root)
    pathfm.wait_for_selection(["documents"], directory=root)
    pathfm.wait_for_focused_entry("documents")
    if mode == "Columns":
        assert "documents" not in pathfm.pane_names(), "the child column stays closed"

    pathfm.keyboard.press("alt+Left")
    pathfm.wait_for_directory("documents")

    pathfm.keyboard.press("alt+Right")
    pathfm.wait_for_directory(root)
    pathfm.wait_for_selection(["documents"], directory=root)
    pathfm.wait_for_focused_entry("documents")
    if mode == "Columns":
        assert "documents" not in pathfm.pane_names(), "the child column stays closed"


@pytest.mark.preferences(browser_mode="columns")
def test_columns_return_selects_the_source_folder_at_any_depth(pathfm):
    root = pathfm.fixture.root.name
    # "aaa" lists first, so a return that ignores the source folder selects it.
    for name in ["aaa", "deep"]:
        folder = pathfm.fixture.path("documents") / name
        folder.mkdir()
        (folder / "leaf.txt").write_text("leaf\n")
    pathfm.keyboard.press("F5")
    pathfm.open_directory("documents")
    pathfm.open_directory("deep", directory="documents")
    pathfm.wait_for_directory("deep")

    crumb = pathfm.wait(
        lambda: pathfm.window.find(role="button", name="documents"),
        "the documents breadcrumb",
    )
    pathfm.pointer.click(crumb)
    pathfm.wait_for_directory("documents")
    pathfm.wait_for_selection(["deep"], directory="documents")
    pathfm.wait_for_focused_entry("deep")
    assert "deep" not in pathfm.pane_names(), "the child column stays closed"

    pathfm.keyboard.press("BackSpace")
    pathfm.wait_for_directory(root)
    pathfm.wait_for_selection(["documents"], directory=root)
    pathfm.wait_for_focused_entry("documents")
    assert "documents" not in pathfm.pane_names(), "the child column stays closed"


@pytest.mark.parametrize("mode", SINGLE_PANE_MODES)
@pytest.mark.parametrize("return_key", ["alt+Left", "alt+Up"])
@pytest.mark.parametrize("enter_with", ["keyboard", "pointer"])
def test_return_restores_nested_scroll_selection_and_keyboard_cursor(
    pathfm, mode, return_key, enter_with
):
    def populate(parent):
        for index in range(160):
            (parent / f"folder-{index:03}").mkdir()

    def scroll_and_enter(parent, clicks):
        container = pathfm.wait(pathfm.entry_container, "the loaded directory listing")
        viewport = next(
            node.screen_bounds()
            for node in container.ancestors()
            if node.role == "scroll pane"
        )
        pathfm.pointer.scroll(at=viewport.center, clicks=clicks)

        def middle_entry():
            visible = [
                node for node in pathfm.entries()
                if viewport.y < node.screen_bounds().y
                < viewport.y + viewport.height - node.screen_bounds().height
            ]
            if visible and visible[0].name != "folder-000":
                return visible[len(visible) // 2]
            return None

        marker = pathfm.wait(middle_entry, "a scrolled directory viewport")
        name = marker.name
        populate(parent / name)
        pathfm.select_entry(name)
        pathfm.wait_for_focused_entry(name)
        y = pathfm.settle(pathfm.entry(name)).screen_bounds().y
        if enter_with == "keyboard":
            pathfm.keyboard.press("Return")
        else:
            pathfm.open_directory(name)
        pathfm.wait_for_directory(name)
        return name, y

    parent = pathfm.fixture.path("archive")
    populate(parent)
    pathfm.open_directory("archive")
    first, first_y = scroll_and_enter(parent, 18)
    second, second_y = scroll_and_enter(parent / first, 10)

    for directory, name, y in [(first, second, second_y), ("archive", first, first_y)]:
        pathfm.keyboard.press(return_key)
        pathfm.wait_for_directory(directory)
        pathfm.wait_for_selection([name])
        pathfm.wait_for_focused_entry(name)
        restored = pathfm.settle(pathfm.entry(name))
        assert abs(restored.screen_bounds().y - y) <= 2, "restore the viewport, not just reveal the selection"
        next_name = f"folder-{int(name.removeprefix('folder-')) + 1:03}"
        pathfm.keyboard.press(NEXT_ENTRY_KEY[mode])
        pathfm.wait_for_focused_entry(next_name)
        pathfm.wait_for_selection([next_name])


@pytest.mark.parametrize("mode", SINGLE_PANE_MODES)
def test_refresh_keeps_the_keyboard_cursor_and_viewport(pathfm, mode):
    archive = pathfm.fixture.path("archive")
    for index in range(160):
        (archive / f"folder-{index:03}").mkdir()
    pathfm.open_directory("archive")
    pathfm.wait_for_directory("archive")
    pathfm.keyboard.press("End")
    pathfm.wait_for_focused_entry("folder-159")

    pathfm.keyboard.press("F5")
    pathfm.wait_for_focused_entry("folder-159")
    pathfm.wait_for_selection(["folder-159"])
    assert pathfm.on_screen(pathfm.entry("folder-159")), "the cursor row stays in view"
    pathfm.keyboard.press(PREVIOUS_ENTRY_KEY[mode])
    pathfm.wait_for_focused_entry("folder-158")
    pathfm.wait_for_selection(["folder-158"])


@pytest.mark.parametrize("mode", SINGLE_PANE_MODES)
def test_refresh_keeps_focus_in_an_empty_pane_filter(pathfm, mode):
    archive = pathfm.fixture.path("archive")
    for index in range(160):
        (archive / f"folder-{index:03}").mkdir()
    pathfm.open_directory("archive")
    pathfm.wait_for_directory("archive")
    pathfm.keyboard.press("ctrl+f")
    field = pathfm.editable_field()

    pathfm.keyboard.press("F5")
    # The reload hides the field with the rows; GTK moves focus off it after the next
    # paint unless the reload hands it back. Several steady samples outlast both.
    steady: list[bool] = []

    def keeps_focus() -> bool:
        steady.append(field.has_state("focused") and field.has_state("showing"))
        del steady[:-10]
        return len(steady) == 10 and all(steady)

    pathfm.wait(keeps_focus, "the filter field to keep focus across the reload")
    pathfm.keyboard.type_text("f")
    pathfm.wait(lambda: field.text == "f", "typing to reach the filter field")


@pytest.mark.preferences(browser_mode="list")
def test_list_typed_file_path_beats_the_restored_position(pathfm):
    root = pathfm.fixture.root.name
    target = pathfm.fixture.path("documents") / "zz-typed-target.txt"
    target.write_text("typed target\n")

    pathfm.open_directory("documents")
    pathfm.wait_for_focused_entry("notes.txt")
    pathfm.keyboard.press("Down")
    pathfm.wait_for_focused_entry("report.md")
    pathfm.keyboard.press("alt+Left")
    pathfm.wait_for_directory(root)

    pathfm.keyboard.press("ctrl+l")
    field = pathfm.editable_field()
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text(str(target))
    pathfm.wait(lambda: field.text == str(target), "the typed file path")
    pathfm.keyboard.press("Return")
    pathfm.wait_for_directory("documents")
    pathfm.wait_for_selection([target.name])
    pathfm.wait_for_focused_entry(target.name)


@pytest.mark.parametrize("mode", ALL_MODES)
def test_shift_arrow_extends_the_selection(pathfm, mode):
    pathfm.select_entry("readme.md")
    pathfm.wait_for_focused_entry("readme.md")

    pathfm.keyboard.press(f"shift+{NEXT_ENTRY_KEY[mode]}")

    pathfm.wait(
        lambda: pathfm.selected_names() == ["readme.md", "todo.txt"],
        "shift and an arrow to extend the selection",
    )

    pathfm.keyboard.press(f"shift+{PREVIOUS_ENTRY_KEY[mode]}")
    pathfm.wait(
        lambda: pathfm.selected_names() == ["readme.md"],
        "shift and the opposite arrow to shrink the selection again",
    )


@pytest.mark.parametrize("mode", COLUMNS_AND_ONE)
def test_select_all_selects_every_entry(pathfm, mode):
    pathfm.select_entry("readme.md")

    pathfm.keyboard.press("ctrl+a")

    pathfm.wait(
        lambda: pathfm.selected_names() == ROOT_ENTRIES,
        "Ctrl+A to select every entry in the pane",
    )


@pytest.mark.preferences(browser_mode="columns", single_click_previews=False)
def test_columns_home_and_end_mirror_the_cursor(pathfm):
    root = pathfm.fixture.root.name
    pathfm.select_entry_with_keyboard("documents")
    pathfm.wait(lambda: pathfm.pane_names() == [root, "documents"], "the child column to open")

    pathfm.keyboard.press("End")
    pathfm.wait_for_focused_entry("todo.txt")
    pathfm.wait(lambda: pathfm.pane_names() == [root], "the stale child column to close")
    assert pathfm.current_directory() == root

    pathfm.keyboard.press("Up")
    pathfm.wait_for_focused_entry("readme.md")
    pathfm.keyboard.press("Up")
    pathfm.wait_for_focused_entry("pictures")
    pathfm.wait(lambda: pathfm.pane_names() == [root, "pictures"], "Up to mirror the folder")

    pathfm.keyboard.press("Home")
    pathfm.wait_for_focused_entry("archive")
    pathfm.wait(
        lambda: pathfm.pane_names() == [root, "archive"], "Home to mirror the first folder"
    )


def test_focus_stays_usable_after_changing_views(pathfm):
    pathfm.select_entry("readme.md")
    pathfm.wait_for_focused_entry("readme.md")

    pathfm.keyboard.press("ctrl+3")
    pathfm.wait_for_view("List")

    pathfm.wait_for_focused_entry("readme.md")
    pathfm.keyboard.press("Down")
    pathfm.wait_for_focused_entry("todo.txt")

    pathfm.keyboard.press("ctrl+1")
    pathfm.wait_for_view("Columns")
    pathfm.keyboard.press("Up")
    pathfm.wait_for_focused_entry("readme.md")


def test_keyboard_only_copy_and_paste_round_trip(pathfm):
    """A complete file operation without ever touching the pointer."""

    fixture = pathfm.fixture
    pathfm.keyboard.press("Down")
    pathfm.wait(lambda: pathfm.focused_name() is not None, "initial keyboard focus")

    pathfm.keyboard.press("End")
    pathfm.wait_for_focused_entry("todo.txt")
    pathfm.keyboard.press("ctrl+c")

    pathfm.keyboard.press("Home")
    pathfm.wait_for_focused_entry("archive")
    pathfm.keyboard.press("Return")
    pathfm.wait_for_directory("archive")
    pathfm.keyboard.press("ctrl+v")

    pathfm.wait(
        lambda: fixture.path("archive/todo.txt").exists(),
        "the keyboard-only paste to land",
    )
    assert fixture.path("todo.txt").exists(), "a copy must leave the source alone"
