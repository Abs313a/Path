# SPDX-License-Identifier: MIT
"""Copy, cut, and paste through both the keyboard and the context menu."""

from __future__ import annotations

import pytest

from harness.keyboard_layout import CAPS_LOCK, RUSSIAN, US
from harness.modes import ALL_MODES, SINGLE_PANE_MODES

# Shortcuts are read before a view acts on them, so other layouts need one view.
COPY_CASES = [
    pytest.param(mode.values[0], US, marks=mode.marks, id=mode.id) for mode in ALL_MODES
] + [
    pytest.param(
        "Columns",
        layout,
        marks=pytest.mark.preferences(browser_mode="columns"),
        id=f"columns-{layout.name}",
    )
    for layout in (RUSSIAN, CAPS_LOCK)
]


@pytest.mark.parametrize(
    "source, duplicate",
    [
        ("todo.txt", "todo (1).txt"),
        ("documents", "documents (1)"),
    ],
)
def test_same_folder_copy_creates_a_numbered_duplicate(pathfm, source, duplicate):
    fixture = pathfm.fixture
    pathfm.select_entry_with_keyboard(source)
    pathfm.keyboard.press("ctrl+d")
    pathfm.wait(lambda: fixture.path(duplicate).exists(), "the numbered copy")
    pathfm.entry(duplicate, directory=fixture.root.name)
    assert fixture.path(source).exists()
    if source == "documents":
        copied_file = fixture.path(f"{duplicate}/notes.txt")
        expected = fixture.path("documents/notes.txt").read_bytes()
    else:
        copied_file = fixture.path(duplicate)
        expected = b"todo\n"
    pathfm.wait(
        lambda: copied_file.is_file() and copied_file.read_bytes() == expected,
        "the numbered copy's contents to finish copying",
    )


@pytest.mark.parametrize("mode, layout", COPY_CASES)
def test_copy_leaves_the_source_in_place(pathfm, keyboard_layout, mode, layout):
    assert pathfm.view_mode() == mode
    fixture = pathfm.fixture

    pathfm.select_entry("todo.txt")
    with keyboard_layout(layout):
        pathfm.keyboard.press("ctrl+c")
        pathfm.open_directory("archive")
        pathfm.paste_into("archive")
        pathfm.wait(
            lambda: (fixture.path("archive/todo.txt")).exists(),
            "the copy to land in archive",
        )
    assert fixture.path("todo.txt").exists(), "copying must not remove the source"
    assert fixture.path("archive/todo.txt").read_text() == "todo\n"
    pathfm.entry("todo.txt", directory="archive")


@pytest.mark.parametrize("mode", ALL_MODES)
def test_paste_targets_a_single_selected_directory(pathfm, mode):
    fixture = pathfm.fixture

    pathfm.select_entry("todo.txt")
    pathfm.keyboard.press("ctrl+c")
    pathfm.select_entry_with_keyboard("archive")
    pathfm.keyboard.press("ctrl+v")

    pathfm.wait(
        lambda: fixture.path("archive/todo.txt").exists(),
        "the copy to land in the selected folder",
    )
    assert fixture.path("todo.txt").exists()


@pytest.mark.parametrize("mode", ALL_MODES)
def test_paste_into_parent_uses_the_current_directory(pathfm, mode):
    fixture = pathfm.fixture
    root = fixture.root.name

    pathfm.open_directory("documents")
    pathfm.select_entry("notes.txt")
    pathfm.keyboard.press("ctrl+c")
    pathfm.keyboard.press("alt+Up")
    pathfm.wait_for_directory(root)
    if mode != "Columns":
        pathfm.wait_for_selection(["documents"])
    pathfm.keyboard.press("ctrl+v")

    pathfm.wait(
        lambda: fixture.path("notes.txt").exists(),
        "the copy to land in the parent directory",
    )
    assert not fixture.path("archive/notes.txt").exists(), (
        "the auto-selected first folder must not steal the paste"
    )
    assert not fixture.path("documents/notes (1).txt").exists(), (
        "the restored selection must not steal the paste"
    )
    assert fixture.path("documents/notes.txt").exists()


@pytest.mark.parametrize("mode", SINGLE_PANE_MODES)
@pytest.mark.parametrize("selection", ["click", "Home"])
def test_paste_into_explicit_selection_after_returning_to_parent(pathfm, mode, selection):
    fixture = pathfm.fixture
    pathfm.open_directory("documents")
    pathfm.select_entry("notes.txt")
    pathfm.keyboard.press("ctrl+c")
    pathfm.keyboard.press("alt+Up")
    pathfm.wait_for_directory(fixture.root.name)
    pathfm.wait_for_selection(["documents"])
    if selection == "click":
        pathfm.click_entry("documents")
    else:
        pathfm.keyboard.press(selection)
    destination = "documents/notes (1).txt" if selection == "click" else "archive/notes.txt"
    pathfm.keyboard.press("ctrl+v")
    pathfm.wait(
        lambda: fixture.path(destination).exists(),
        "the copy to land in the explicitly selected folder",
    )
    assert not fixture.path("notes.txt").exists()


@pytest.mark.usefixtures("unreserved_columns")
def test_opening_a_child_keeps_paste_under_the_pointer(pathfm):
    fixture = pathfm.fixture

    pathfm.open_directory("documents")
    pathfm.select_entry("notes.txt", directory="documents")
    pathfm.keyboard.press("ctrl+c")
    pathfm.keyboard.press("alt+Up")
    pathfm.wait_for_directory(fixture.root.name)
    pathfm.open_directory("archive")
    pathfm.keyboard.press("ctrl+v")

    pathfm.wait(
        lambda: fixture.path("notes.txt").exists(),
        "the copy to land in the parent column still under the pointer",
    )
    assert not fixture.path("archive/notes.txt").exists()


@pytest.mark.parametrize("mode", ALL_MODES)
def test_cut_moves_only_after_paste(pathfm, mode):
    fixture = pathfm.fixture

    pathfm.select_entry("todo.txt")
    pathfm.keyboard.press("ctrl+x")

    assert fixture.path("todo.txt").exists(), (
        "cut must not touch the filesystem before the paste"
    )

    pathfm.open_directory("archive")
    pathfm.paste_into("archive")

    pathfm.wait(
        lambda: fixture.path("archive/todo.txt").exists(),
        "the cut file to arrive in archive",
    )
    pathfm.wait(
        lambda: not fixture.path("todo.txt").exists(),
        "the cut file to leave its source directory",
    )


@pytest.mark.parametrize("mode", ALL_MODES)
def test_context_menu_copy_and_paste(pathfm, mode):
    fixture = pathfm.fixture

    pathfm.open_context_menu("readme.md")
    assert "Copy" in pathfm.menu_items()
    pathfm.choose_menu_item("Copy")

    pathfm.open_directory("archive")
    _paste_from_context_menu(pathfm)

    pathfm.wait(
        lambda: fixture.path("archive/readme.md").exists(),
        "the context-menu copy to land in archive",
    )
    assert fixture.path("readme.md").exists()


@pytest.mark.parametrize("mode", ALL_MODES)
def test_context_menu_cut_and_paste(pathfm, mode):
    fixture = pathfm.fixture

    pathfm.open_context_menu("readme.md")
    pathfm.choose_menu_item("Cut")
    pathfm.open_directory("archive")
    _paste_from_context_menu(pathfm)

    pathfm.wait(
        lambda: fixture.path("archive/readme.md").exists()
        and not fixture.path("readme.md").exists(),
        "the context-menu cut to complete",
    )


def _paste_from_context_menu(pathfm):
    pathfm.pointer.right_click(pathfm.pane("archive"), at=pathfm.background_point("archive"))
    pathfm.wait(pathfm.context_menu, "the destination context menu")
    pathfm.choose_menu_item("Paste")


def test_skipping_one_collision_still_pastes_the_rest(pathfm):
    fixture = pathfm.fixture
    fixture.path("archive/notes.txt").write_text("existing\n")
    pathfm.open_directory("documents")
    pathfm.select_entry_with_keyboard("notes.txt")
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.press("ctrl+c")
    pathfm.keyboard.press("alt+Up")
    pathfm.wait_for_directory(fixture.root.name)
    pathfm.open_directory("archive")
    pathfm.paste_into("archive")

    dialog = pathfm.wait_for_dialog()
    assert dialog.name == "File already exists", (
        "a duplicate name must be surfaced rather than silently resolved"
    )
    assert dialog.find(role="button", name="Skip") is not None, (
        "skip must stay available when other items are already accepted"
    )
    assert dialog.find(name="Apply to All") is None, (
        "apply to all has no further conflicts left to apply to"
    )

    pathfm.pointer.click(pathfm.dialog_button("Skip"))
    pathfm.wait(lambda: pathfm.dialog() is None, "the conflict dialog to close")
    assert fixture.path("archive/notes.txt").read_text() == "existing\n", (
        "skipping must leave the conflicting file alone"
    )
    assert not fixture.path("archive/notes (1).txt").exists(), (
        "skipping must not create a numbered copy"
    )
    for name in ("report.md", "spreadsheet.csv"):
        source = fixture.path(f"documents/{name}")
        copied = fixture.path(f"archive/{name}")
        pathfm.wait(
            lambda: copied.is_file() and copied.read_bytes() == source.read_bytes(),
            f"the non-conflicting {name} copy to finish",
        )


def test_replacing_on_a_duplicate_name_overwrites(pathfm):
    fixture = pathfm.fixture
    fixture.path("archive/todo.txt").write_text("existing\n")

    pathfm.select_entry("todo.txt")
    pathfm.keyboard.press("ctrl+c")
    pathfm.open_directory("archive")
    pathfm.paste_into("archive")

    pathfm.wait_for_dialog()
    pathfm.pointer.click(pathfm.dialog_button("Replace"))

    pathfm.wait(
        lambda: fixture.path("archive/todo.txt").read_text() == "todo\n",
        "the replaced file to take the pasted contents",
    )
    assert fixture.path("todo.txt").exists(), "the copy source must survive"


def test_paste_availability_follows_the_clipboard(pathfm):
    def paste_is_enabled() -> bool:
        pathfm.pointer.right_click(pathfm.pane(), at=pathfm.background_point())
        pathfm.wait(pathfm.context_menu, "the pane context menu")
        enabled = pathfm.menu_item("Paste").has_state("sensitive")
        pathfm.dismiss_menu()
        return enabled

    assert not paste_is_enabled(), (
        "Paste should be offered but disabled while the clipboard is empty"
    )

    pathfm.select_entry("todo.txt")
    pathfm.keyboard.press("ctrl+c")

    assert paste_is_enabled(), "copying should enable Paste"


def test_copying_a_directory_copies_its_contents(pathfm):
    fixture = pathfm.fixture

    # Through the context menu: in Columns a plain click on a folder opens it.
    pathfm.open_context_menu("documents")
    pathfm.choose_menu_item("Copy")
    pathfm.open_directory("archive")
    pathfm.paste_into("archive")

    pathfm.wait(
        lambda: fixture.path("archive/documents/notes.txt").exists(),
        "the directory copy to include its contents",
    )
    assert sorted(fixture.names("archive/documents")) == [
        "notes.txt",
        "report.md",
        "spreadsheet.csv",
    ]
    assert fixture.path("documents/notes.txt").exists()
