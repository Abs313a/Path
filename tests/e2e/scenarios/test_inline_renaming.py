# SPDX-License-Identifier: MIT
"""Immediate creation and consistent file/folder rename finalization."""

import time

import pytest

from harness.artifacts import ArtifactCollector
from harness.keyboard_layout import PINYIN, RUSSIAN_ONLY, US
from harness.modes import ALL_MODES, COLUMNS_AND_ONE
from harness.screenshots import capture
from harness.tree import Atspi

KINDS = ["file", "folder"]


def _cases_for_modes(modes, kind, new, target):
    new_id = "new" if new else "existing"
    return [
        pytest.param(
            mode.values[0],
            kind,
            new,
            target,
            marks=mode.marks,
            id=f"{target}-{new_id}-{kind}-{mode.id}",
        )
        for mode in modes
    ]


# Enter and sidebar have extra postconditions. The four click-away targets share
# disk + editor-closed asserts, so they run in Columns + List on one lifecycle.
VALID_NAME_COMMIT_CASES = [
    case
    for target in ("enter", "sidebar")
    for kind in KINDS
    for new in (False, True)
    for case in _cases_for_modes(ALL_MODES, kind, new, target)
] + [
    case
    for target in ("file", "folder", "background", "tab")
    for case in _cases_for_modes(COLUMNS_AND_ONE, "file", False, target)
]


@pytest.mark.preferences(single_click_previews=False)
@pytest.mark.parametrize("mode", ALL_MODES)
def test_long_rename_keeps_caret_visible(pathfm, mode, request):
    name = "synthetic-quarterly-report-with-a-very-long-descriptive-basename-2026.txt"
    pathfm.fixture.path(name).write_text("keep\n")
    pathfm.keyboard.press("F5")
    pathfm.entry(name)
    pathfm.select_entry_with_keyboard(name)
    bounds = pathfm.window.window_bounds()
    width = 420 if mode == "Columns" else 640
    pathfm.keyboard.connection.resize_surface(bounds.width, bounds.height, width, 300)
    pathfm.wait(lambda: pathfm.window.window_bounds().width == width, "a narrow window")
    pathfm.keyboard.press("F2")
    field = rename_field(pathfm)
    text = Atspi.Accessible.get_text_iface(field.accessible)
    assert text is not None
    selection = Atspi.Text.get_selection(text, 0)
    assert (selection.start_offset, selection.end_offset) == (0, len(name) - 4)

    def assert_editor_constrained():
        bounds = field.window_bounds()
        window = pathfm.window.window_bounds()
        pane = pathfm.pane().window_bounds()
        assert bounds.height > 0 and pane.x <= bounds.x < window.width
        # The Rust fixture checks exact GtkText/caret bounds; here reject
        # oversized bounds from the external accessibility interface.
        assert 0 < bounds.width <= window.width - pane.x

    assert field.window_bounds().width > 0
    pathfm.keyboard.press("End")
    pathfm.wait(lambda: Atspi.Text.get_caret_offset(text) == len(name), "End to reach the extension")
    assert Atspi.Text.get_n_selections(text) == 0
    if request.config.getoption("--keep-artifacts"):
        collector = ArtifactCollector(test_name=request.node.name)
        capture(pathfm.display.display, collector.directory / "after-end.png")
    assert_editor_constrained()
    pathfm.keyboard.type_text("-final")
    pathfm.wait(lambda: field.text == name + "-final", "typing after the extension")
    pathfm.wait(lambda: Atspi.Text.get_caret_offset(text) == len(name) + 6, "the caret to follow typing")
    assert_editor_constrained()
    pathfm.keyboard.press_repeatedly("BackSpace", 6)
    pathfm.wait(lambda: field.text == name, "Backspace to remove the appended text")
    pathfm.keyboard.press("Left")
    pathfm.wait(lambda: Atspi.Text.get_caret_offset(text) == len(name) - 1, "Left to move the caret")
    pathfm.keyboard.press("Right")
    pathfm.wait(lambda: Atspi.Text.get_caret_offset(text) == len(name), "Right to return to the end")
    assert_editor_constrained()
    pathfm.pointer.click(field)
    pathfm.wait(lambda: 0 < Atspi.Text.get_caret_offset(text) < len(name), "clicking inside the visible name to move the caret")
    assert_editor_constrained()
    pathfm.keyboard.press("End")
    pathfm.wait(lambda: Atspi.Text.get_caret_offset(text) == len(name), "End after clicking")
    pathfm.keyboard.press("Return")
    wait_for_edit_closed(pathfm)
    assert pathfm.fixture.path(name).read_text() == "keep\n"
    assert not pathfm.fixture.path(name + "-final").exists()


def name_text_point(pathfm, name, mode):
    label = pathfm.entry(name).find(role="label", name=name)
    assert label is not None, f"no name label on {name!r}"
    bounds = label.screen_bounds()
    # Row labels left-align their text; the icons caption centers it.
    return bounds.center if mode == "Icons" else (bounds.x + 4, bounds.center[1])


@pytest.mark.parametrize("mode", ALL_MODES)
def test_slow_click_rename_respects_escape_and_selects_the_stem(pathfm, mode):
    pathfm.select_entry_with_keyboard("todo.txt")
    pathfm.pointer.click(pathfm.entry("todo.txt"), at=name_text_point(pathfm, "todo.txt", mode))
    pathfm.keyboard.press("Escape")
    # Outlast GTK's 400ms double-click interval to detect a stale timeout.
    time.sleep(0.6)
    assert pathfm.window.find(role="text", name="Rename", states={"editable"}) is None

    pathfm.select_entry_with_keyboard("todo.txt")
    pathfm.pointer.click(pathfm.entry("todo.txt"), at=name_text_point(pathfm, "todo.txt", mode))
    field = rename_field(pathfm)
    text = Atspi.Accessible.get_text_iface(field.accessible)
    selection = Atspi.Text.get_selection(text, 0)
    assert (selection.start_offset, selection.end_offset) == (0, len("todo"))
    assert field.text == "todo.txt"
    assert pathfm.fixture.path("todo.txt").exists()


@pytest.mark.parametrize(
    "mode,target",
    [
        pytest.param(
            mode.values[0], target,
            marks=mode.marks,
            id=f"{target}-{mode.id}",
        )
        for target in ["icon", "name-padding"]
        for mode in ALL_MODES
        # The icons caption band is the name label, so name-padding+Icons is
        # not a meaningful combination; exclude it from collection.
        if not (target == "name-padding" and mode.id == "icons")
    ],
)
def test_slow_click_away_from_the_name_does_not_rename(pathfm, mode, target):
    pathfm.select_entry_with_keyboard("todo.txt")
    entry = pathfm.entry("todo.txt")
    if target == "icon":
        icon = entry.find(role="image")
        assert icon is not None
        point = icon.screen_bounds().center
    else:
        point = pathfm.pointer.row_whitespace_point(entry, "todo.txt")
    pathfm.pointer.click(entry, at=point)
    time.sleep(0.6)
    assert pathfm.window.find(role="text", name="Rename", states={"editable"}) is None
    assert pathfm.selected_names() == ["todo.txt"]


@pytest.mark.preferences(browser_mode="columns")
@pytest.mark.usefixtures("unreserved_columns")
def test_columns_reclick_open_folder_name_renames_and_empty_space_closes(pathfm):
    root = pathfm.fixture.root.name
    pathfm.pointer.click(pathfm.entry("documents"))
    pathfm.wait(
        lambda: pathfm.pane().name == "documents",
        "one click to open the folder column",
    )
    time.sleep(0.6)

    pathfm.pointer.click(
        pathfm.entry("documents", root),
        at=name_text_point(pathfm, "documents", "Columns"),
    )
    rename_field(pathfm)
    pathfm.keyboard.press("Escape")
    wait_for_edit_closed(pathfm)

    pathfm.pointer.click(pathfm.pane(root), at=pathfm.background_point(root))
    pathfm.wait(
        lambda: pathfm.pane_names() == [root],
        "empty space to close the child column",
    )
    pathfm.entry("documents", root)


def rename_field(pathfm):
    return pathfm.wait(
        lambda: pathfm.window.find(role="text", name="Rename", states={"editable", "focused"}),
        "the rename editor to take focus",
    )


def start_creation(pathfm, kind, via_menu=True):
    if via_menu:
        pathfm.pointer.right_click(pathfm.pane(), at=pathfm.background_point())
        pathfm.choose_menu_item("New File" if kind == "file" else "New Folder")
    else:
        pathfm.keyboard.press("ctrl+shift+n")
    return rename_field(pathfm)


def begin_edit(pathfm, kind, new):
    pathfm.select_entry("readme.md")
    if new:
        field = start_creation(pathfm, kind, via_menu=kind == "file")
        original = "new " + kind
    else:
        original = "todo.txt" if kind == "file" else "archive"
        pathfm.select_entry_with_keyboard(original)
        pathfm.keyboard.press("F2")
        field = rename_field(pathfm)
        if kind == "file":
            pathfm.keyboard.press("ctrl+a")
    pathfm.wait(lambda: field.text == original, "the original name to appear")
    path = pathfm.fixture.path(original)
    assert path.is_file() if kind == "file" else path.is_dir()
    return field, original


def wait_for_edit_closed(pathfm):
    pathfm.wait(
        lambda: pathfm.window.find(role="text", name="Rename", states={"editable"}) is None,
        "the name editor to close",
    )
    assert "Gtk-CRITICAL" not in pathfm.application.log()


# The rename handler owns Ctrl+A. Ctrl+X and Ctrl+V reach the text field, where
# a Russian-only keymap leaves GTK's own bindings no Latin key to match.
NEW_ITEM_CASES = [
    pytest.param(kind, via_menu, US, id=f"{kind}-{via_menu}")
    for kind, via_menu in [("folder", False), ("folder", True), ("file", True)]
] + [pytest.param("file", True, RUSSIAN_ONLY, id="file-True-ru-only")]


@pytest.mark.parametrize("kind,via_menu,layout", NEW_ITEM_CASES)
def test_new_item_exists_before_typing_and_backspace_clears_its_selected_name(
    pathfm, keyboard_layout, kind, via_menu, layout
):
    pathfm.select_entry("readme.md")
    field = start_creation(pathfm, kind, via_menu)
    original = "new " + kind
    pathfm.wait(lambda: field.text == original, "the default name to appear")
    path = pathfm.fixture.path(original)
    assert path.is_dir() if kind == "folder" else path.is_file()
    if kind == "file":
        assert path.read_bytes() == b""
    pathfm.keyboard.press("End")
    with keyboard_layout(layout):
        pathfm.keyboard.press("ctrl+a")
        pathfm.keyboard.press("ctrl+x")
        pathfm.wait(lambda: field.text == "", "Ctrl+A and Ctrl+X to cut the entire default name")
        pathfm.keyboard.press("ctrl+v")
        pathfm.wait(lambda: field.text == original, "Ctrl+V to paste the default name back")
        pathfm.keyboard.press("ctrl+a")
        pathfm.keyboard.press("BackSpace")
        pathfm.wait(lambda: field.text == "", "Ctrl+A and Backspace to clear the entire default name")
    pathfm.keyboard.press("Return")
    wait_for_edit_closed(pathfm)
    pathfm.entry(original)
    assert path.exists()


def test_new_item_uses_the_first_free_number_without_overwriting(pathfm):
    base = "new file"
    pathfm.fixture.path(base).write_text("keep\n")
    pathfm.fixture.path(base + " (1)").symlink_to("missing")
    pathfm.fixture.path(base + " (2)").mkdir()
    pathfm.keyboard.press("F5")
    for name in (base, base + " (1)", base + " (2)"):
        pathfm.entry(name)
    # Fixture insertions move rows; select by keyboard after the refreshed inventory.
    pathfm.select_entry_with_keyboard("readme.md")
    field = start_creation(pathfm, "file")
    pathfm.wait(lambda: field.text == base + " (3)", "the first available numbered name")
    created = pathfm.fixture.path(base + " (3)")
    assert created.is_file()
    pathfm.keyboard.press("Escape")
    wait_for_edit_closed(pathfm)
    assert pathfm.fixture.path(base).read_text() == "keep\n"
    assert pathfm.fixture.path(base + " (1)").is_symlink()
    assert pathfm.fixture.path(base + " (2)").is_dir()
    assert created.exists()


@pytest.mark.parametrize("mode,kind,new,target", VALID_NAME_COMMIT_CASES)
def test_leaving_a_valid_name_commits_it(pathfm, mode, kind, new, target):
    if kind == "folder" and not new:
        pathfm.fixture.path("archive/marker.txt").write_text("keep\n")
    field, original = begin_edit(pathfm, kind, new)
    original_path = pathfm.fixture.path(original)
    contents = original_path.read_bytes() if kind == "file" else None
    pathfm.keyboard.type_text("renamed.item")
    pathfm.wait(lambda: field.text == "renamed.item", "typing to replace the selection")
    if target == "sidebar":
        pathfm.pointer.click(pathfm.sidebar_button("Home"))
    elif target == "background":
        pathfm.pointer.click(pathfm.pane(), at=pathfm.background_point())
    elif target in ("tab", "enter"):
        pathfm.keyboard.press("Tab" if target == "tab" else "Return")
    else:
        pathfm.pointer.click(pathfm.entry("readme.md" if target == "file" else "documents"))
    renamed = pathfm.fixture.path("renamed.item")
    pathfm.wait(renamed.exists, "the rename on disk")
    wait_for_edit_closed(pathfm)
    assert not original_path.exists()
    if kind == "file":
        assert renamed.read_bytes() == contents
    else:
        assert renamed.is_dir()
        if not new:
            assert (renamed / "marker.txt").read_text() == "keep\n"
    if target == "enter":
        pathfm.entry("renamed.item")
    if target == "sidebar":
        pathfm.wait_for_directory(pathfm.environment.home.name)
        assert not (pathfm.environment.home / "renamed.item").exists()


@pytest.mark.parametrize("kind", KINDS)
def test_rename_and_undo_restores_the_original_item(pathfm, kind):
    if kind == "folder":
        pathfm.fixture.path("archive/marker.txt").write_text("keep\n")
    field, original = begin_edit(pathfm, kind, False)
    original_path = pathfm.fixture.path(original)
    pathfm.keyboard.type_text("undo-target")
    pathfm.wait(lambda: field.text == "undo-target", "the replacement name")
    pathfm.keyboard.press("Return")
    wait_for_edit_closed(pathfm)
    renamed_path = pathfm.fixture.path("undo-target")
    pathfm.wait(renamed_path.exists, "the renamed item")
    # The filesystem changes before the UI callback publishes rename undo.
    pathfm.wait_for_selection(["undo-target"], pathfm.fixture.root.name)
    pathfm.wait(lambda: pathfm.focused_name() == "undo-target", "the committed rename cursor")

    pathfm.keyboard.press("ctrl+z")
    pathfm.wait(
        lambda: original_path.exists() and not renamed_path.exists(),
        "Ctrl+Z to restore the original item",
    )
    if kind == "file":
        assert original_path.read_text() == "todo\n"
    else:
        assert (original_path / "marker.txt").read_text() == "keep\n"


@pytest.mark.parametrize("action", ["enter", "click"])
def test_invalid_names_retain_the_original(pathfm, action):
    name = "bad/name"
    field, original = begin_edit(pathfm, "file", False)
    path = pathfm.fixture.path(original)
    contents = path.read_bytes()
    pathfm.keyboard.press("BackSpace")
    pathfm.keyboard.type_text(name)
    pathfm.wait(lambda: field.text == name, "the proposed name to appear")
    if action == "enter":
        pathfm.keyboard.press("Return")
    else:
        pathfm.pointer.click(pathfm.pane(), at=pathfm.background_point())
    wait_for_edit_closed(pathfm)
    pathfm.entry(original)
    assert path.exists()
    assert path.read_bytes() == contents
    assert not pathfm.fixture.path("bad").exists()


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("new", [False, True], ids=["existing", "new"])
def test_escape_preserves_the_original_name(pathfm, kind, new):
    field, original = begin_edit(pathfm, kind, new)
    pathfm.keyboard.type_text("discarded")
    pathfm.wait(lambda: field.text == "discarded", "the proposed name to appear")
    pathfm.keyboard.press("Escape")
    wait_for_edit_closed(pathfm)
    pathfm.entry(original)
    assert pathfm.fixture.path(original).exists()
    assert not pathfm.fixture.path("discarded").exists()


@pytest.mark.parametrize("mode", ALL_MODES)
@pytest.mark.parametrize("kind", KINDS)
def test_new_item_clears_a_filter_that_would_hide_its_editor(pathfm, mode, kind):
    pathfm.select_entry("readme.md")
    pathfm.keyboard.press("ctrl+f")
    filter_field = pathfm.editable_field()
    pathfm.keyboard.type_text("no-matching-entry")
    pathfm.wait(lambda: filter_field.text == "no-matching-entry", "the filter query")
    pathfm.wait(lambda: pathfm.entry_names() == [], "the filter to hide existing entries")
    field = start_creation(pathfm, kind, via_menu=kind == "file")
    original = "new " + kind
    pathfm.wait(lambda: field.text == original, "the visible rename editor")
    assert filter_field.text == ""
    assert pathfm.fixture.path(original).exists()
    pathfm.keyboard.press("Escape")
    pathfm.entry(original)


@pytest.mark.parametrize("mode", COLUMNS_AND_ONE)
@pytest.mark.parametrize("kind", KINDS)
def test_repeated_renames_select_the_folder_name_or_file_stem(pathfm, mode, kind):
    original = "archive" if kind == "folder" else "todo.txt"
    for index in range(1, 4):
        pathfm.select_entry("readme.md")
        pathfm.select_entry_with_keyboard(original)
        pathfm.keyboard.press("F2")
        field = rename_field(pathfm)
        typed = f"archive.v{index}" if kind == "folder" else f"version-{index}"
        replacement = typed if kind == "folder" else typed + ".txt"
        pathfm.keyboard.type_text(typed)
        pathfm.wait(lambda: field.text == replacement, "the intended part of the name to be replaced")
        pathfm.keyboard.press("Return")
        pathfm.wait(lambda: pathfm.fixture.path(replacement).exists(), "the renamed entry")
        pathfm.entry(replacement)
        assert not pathfm.fixture.path(original).exists()
        if kind == "file":
            assert pathfm.fixture.path(replacement).read_text() == "todo\n"
        original = replacement


def test_escape_cancels_a_tone_mark_composition_before_the_rename(pathfm, keyboard_layout):
    field, original = begin_edit(pathfm, "file", False)
    with keyboard_layout(PINYIN):
        pathfm.keyboard.type_text("m")
        pathfm.keyboard.press("altgr+1")
        pathfm.keyboard.type_text("a")
        pathfm.wait(lambda: field.text == "mā", "AltGr+1 then a to type ā")
        pathfm.keyboard.press("altgr+3")
        pathfm.keyboard.press("Escape")
        pathfm.keyboard.type_text("o")
        pathfm.wait(lambda: field.text == "māo", "Escape to cancel only the pending tone mark")
    pathfm.keyboard.press("Return")
    pathfm.wait(lambda: pathfm.fixture.path("māo").exists(), "the composed name on disk")
    wait_for_edit_closed(pathfm)
    assert not pathfm.fixture.path(original).exists()


# F5 reloads the rows each mode leases differently; the other shortcuts never
# touch the listing, so one mode covers them.
WINDOW_ACCELERATOR_CASES = [
    pytest.param("F5", mode.values[0], marks=mode.marks, id=f"f5-{mode.id}") for mode in ALL_MODES
] + [
    pytest.param(chord, "Columns", marks=pytest.mark.preferences(browser_mode="columns"), id=f"{name}-columns")
    for chord, name in [("ctrl+\\", "ctrl-backslash"), ("ctrl+k", "ctrl-k")]
]


@pytest.mark.preferences(arrow_navigation_scoped=True, single_click_previews=False)
@pytest.mark.parametrize("chord,mode", WINDOW_ACCELERATOR_CASES)
def test_window_accelerators_leave_an_open_rename_alone(pathfm, chord, mode):
    field, original = begin_edit(pathfm, "file", False)
    pathfm.keyboard.type_text("abc")
    pathfm.wait(lambda: field.text == "abc", "typing to replace the selection")
    pathfm.keyboard.press(chord)
    # Give a misrouted accelerator time to act before asserting nothing changed.
    time.sleep(0.5)
    editor = pathfm.window.find(role="text", name="Rename", states={"editable", "focused"})
    assert editor is not None and editor.text == "abc", f"{chord} closed the rename or took its focus"
    assert len(pathfm.window.find_all(role="text", states={"editable"})) == 1
    assert pathfm.environment.read_preferences().get("arrow_navigation_scoped") == "true"
    assert pathfm.fixture.path(original).exists()

    pathfm.keyboard.press("Return")
    pathfm.wait(lambda: pathfm.fixture.path("abc").exists(), "the typed name to be committed")
    wait_for_edit_closed(pathfm)
