# SPDX-License-Identifier: MIT
"""Escape dismisses transient UI before clearing the active pane selection."""

import pytest

from harness.modes import ALL_MODES, NEXT_ENTRY_KEY

TRANSIENT_SURFACES = [
    "menu",
    "properties",
    "rename",
    "new-folder",
    "new-file",
    "location",
    "filter",
    "preview",
]
MODE_DEPENDENT_TRANSIENTS = {"new-folder", "preview", "rename"}


def _transient_dismiss_cases():
    cases = []
    for surface in TRANSIENT_SURFACES:
        modes = ALL_MODES if surface in MODE_DEPENDENT_TRANSIENTS else [
            mode for mode in ALL_MODES if mode.id == "columns"
        ]
        for mode in modes:
            cases.append(
                pytest.param(
                    mode.values[0],
                    surface,
                    marks=mode.marks,
                    id=f"{surface}-{mode.id}",
                )
            )
    return cases


@pytest.mark.parametrize("mode", ALL_MODES)
@pytest.mark.parametrize("multiple", [False, True])
@pytest.mark.preferences(single_click_previews=False)
def test_escape_clears_selection_without_navigation(pathfm, mode, multiple):
    root = pathfm.fixture.root.name
    if multiple:
        pathfm.select_entry("todo.txt", root)
        pathfm.click_entry_with("readme.md", ["ctrl"], root)
    else:
        pathfm.select_entry("readme.md", root)
    focused = "readme.md"
    pathfm.wait_for_selection(["readme.md", "todo.txt"] if multiple else [focused], root)
    panes = pathfm.pane_names()

    pathfm.keyboard.press("Escape")

    pathfm.wait_for_selection([], root)
    pathfm.wait_for_focused_entry(focused)
    assert pathfm.pane_names() == panes
    pathfm.keyboard.press(NEXT_ENTRY_KEY[mode])
    pathfm.wait_for_selection(["todo.txt"], root)
    pathfm.wait_for_focused_entry("todo.txt")


@pytest.mark.parametrize("mode", ALL_MODES)
@pytest.mark.preferences(single_click_previews=False)
def test_enter_after_escape_opens_the_focused_folder(pathfm, mode):
    root = pathfm.fixture.root.name
    pathfm.select_entry_with_keyboard("documents")
    pathfm.wait_for_focused_entry("documents")
    pathfm.keyboard.press("Escape")
    pathfm.wait_for_selection([], root)
    pathfm.wait_for_focused_entry("documents")

    pathfm.keyboard.press("Return")

    pathfm.wait_for_directory("documents")
    pathfm.wait_for_entries(["notes.txt", "report.md", "spreadsheet.csv"], "documents")


@pytest.mark.preferences(browser_mode="columns", single_click_previews=False)
def test_escape_only_clears_the_active_column(pathfm):
    root = pathfm.fixture.root.name
    pathfm.open_directory("documents", directory=root)
    pathfm.select_entry("notes.txt", "documents")
    parent_selection = pathfm.selected_names(root)
    pathfm.keyboard.press("Escape")
    pathfm.wait_for_selection([], "documents")
    assert pathfm.selected_names(root) == parent_selection
    assert pathfm.pane_names() == [root, "documents"]
    pathfm.wait_for_focused_entry("notes.txt")


@pytest.mark.parametrize("mode,surface", _transient_dismiss_cases())
@pytest.mark.preferences(single_click_previews=False)
def test_escape_dismisses_transient_before_selection(pathfm, mode, surface):
    root = pathfm.fixture.root.name
    pathfm.select_entry("readme.md", root)
    if surface in ("menu", "properties"):
        pathfm.open_context_menu("readme.md", root)
        if surface == "properties":
            pathfm.choose_menu_item("Properties")
            pathfm.wait_for_dialog()
    elif surface == "new-file":
        pathfm.pointer.right_click(pathfm.pane(), at=pathfm.background_point())
        pathfm.choose_menu_item("New File")
        pathfm.editable_field()
    elif surface == "preview":
        pathfm.keyboard.press("space")
        pathfm.wait(pathfm.preview, "preview to open")
    else:
        shortcut = {"rename": "F2", "new-folder": "ctrl+shift+n", "location": "ctrl+l", "filter": "ctrl+f"}[surface]
        pathfm.keyboard.press(shortcut)
        pathfm.editable_field()

    pathfm.keyboard.press("Escape")

    if surface == "menu":
        pathfm.wait_for_menu_closed()
    elif surface == "properties":
        pathfm.wait(lambda: pathfm.dialog() is None, "properties to close")
    elif surface == "preview":
        pathfm.wait(lambda: pathfm.preview() is None, "preview to close")
    expected = {"new-folder": "new folder", "new-file": "new file"}.get(surface, "readme.md")
    pathfm.wait_for_selection([expected], root)
    if surface in ("new-folder", "new-file"):
        assert pathfm.fixture.path(expected).exists()
    pathfm.keyboard.press("Escape")
    pathfm.wait_for_selection([], root)
    expected_panes = [root, "new folder"] if mode == "Columns" and surface == "new-folder" else [root]
    assert pathfm.pane_names() == expected_panes


@pytest.mark.parametrize("mode", ALL_MODES)
@pytest.mark.parametrize("had_range", [False, True], ids=["no-range", "had-range"])
@pytest.mark.preferences(single_click_previews=False)
def test_shift_after_escape_starts_on_the_focused_entry(pathfm, mode, had_range):
    root = pathfm.fixture.root.name
    next_key = NEXT_ENTRY_KEY[mode]
    pathfm.wait_for_focused_entry("archive")
    pathfm.wait_for_selection(["archive"], root)
    if had_range:
        pathfm.keyboard.press(f"shift+{next_key}")
        pathfm.wait_for_selection(["archive", "documents"], root)
        pathfm.wait_for_focused_entry("documents")
        focused = "documents"
        first = ["documents"]
        second = ["documents", "pictures"]
    else:
        focused = "archive"
        first = ["archive"]
        second = ["archive", "documents"]

    pathfm.keyboard.press("Escape")
    pathfm.wait_for_selection([], root)
    pathfm.wait_for_focused_entry(focused)

    pathfm.keyboard.press(f"shift+{next_key}")
    pathfm.wait_for_selection(first, root)
    pathfm.wait_for_focused_entry(focused)

    pathfm.keyboard.press(f"shift+{next_key}")
    pathfm.wait_for_selection(second, root)
    pathfm.wait_for_focused_entry(second[-1])


TENXER = pytest.mark.preferences(
    tenxer_mode=True,
    type_to_search=False,
    single_click_previews=False,
    filter_include_subfolders=False,
)
ROOT_ENTRIES = ["archive", "documents", "pictures", "readme.md", "todo.txt"]


def _footer_mark(pathfm, name):
    return pathfm.window.find(role="label", name=name) is not None


@TENXER
@pytest.mark.parametrize("mode", ALL_MODES)
def test_tenxer_escape_dismisses_filter_preview_then_fill(pathfm, mode):
    root = pathfm.fixture.root.name
    pathfm.select_entry("readme.md", root)
    pathfm.keyboard.press("f")
    pathfm.editable_field()
    pathfm.keyboard.type_text("todo")
    pathfm.keyboard.press("Return")
    pathfm.wait(lambda: _footer_mark(pathfm, "filter: todo"), "the filter to commit")
    pathfm.wait_for_focused_entry("todo.txt")
    pathfm.keyboard.press("i")
    pathfm.wait(pathfm.preview, "i to open the preview")
    panes = pathfm.pane_names()

    pathfm.keyboard.press("Escape")
    pathfm.wait(lambda: pathfm.entry_names(root) == ROOT_ENTRIES, "Esc to clear the filter")
    assert not _footer_mark(pathfm, "filter: todo")
    assert pathfm.preview() is not None
    pathfm.wait_for_selection(["readme.md"], root)

    pathfm.keyboard.press("Escape")
    pathfm.wait(lambda: pathfm.preview() is None, "Esc to close the preview")
    pathfm.wait_for_selection(["readme.md"], root)

    pathfm.keyboard.press("Escape")
    pathfm.wait_for_selection([], root)

    pathfm.keyboard.press("Escape")
    pathfm.wait_for_selection([], root)
    assert pathfm.pane_names() == panes
    assert pathfm.entry_names(root) == ROOT_ENTRIES


@TENXER
@pytest.mark.parametrize("mode", ALL_MODES)
def test_tenxer_escape_closes_a_peek_but_never_a_column(pathfm, mode):
    root = pathfm.fixture.root.name
    pathfm.keyboard.press("Home")
    pathfm.wait_for_focused_entry("archive")
    pathfm.keyboard.press("space")
    pathfm.wait_for_selection(["archive"], root)
    pathfm.wait_for_focused_entry("documents")
    pathfm.keyboard.press("i")
    if mode == "Columns":
        pathfm.wait(lambda: pathfm.pane_names() == [root, "documents"], "i to open a column")
    else:
        pathfm.wait(pathfm.peek, "i to open the folder peek")
        pathfm.keyboard.press("Escape")
        pathfm.wait(lambda: pathfm.peek() is None, "Esc to close the peek")
        pathfm.wait_for_selection(["archive"], root)
    panes = pathfm.pane_names()

    pathfm.keyboard.press("Escape")
    pathfm.wait_for_selection([], root)
    pathfm.wait_for_focused_entry("documents")

    pathfm.keyboard.press("Escape")
    pathfm.wait_for_selection([], root)
    assert pathfm.pane_names() == panes
    pathfm.wait_for_focused_entry("documents")
