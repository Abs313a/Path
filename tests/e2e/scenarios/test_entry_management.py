# SPDX-License-Identifier: MIT
"""Creating, renaming, trashing, deleting, and undoing."""

from __future__ import annotations

import re
import tempfile
import time
from pathlib import Path

import pytest
from gi.repository import Gio

from harness.modes import ALL_MODES, COLUMNS_AND_ONE


def start_new_file(pathfm, select=True):
    if select:
        pathfm.select_entry("readme.md")
    pathfm.pointer.right_click(pathfm.pane(), at=pathfm.background_point())
    pathfm.choose_menu_item("New File")
    field = pathfm.editable_field()
    pathfm.wait(lambda: field.text.startswith("new file"), "the created file's editor")
    return field


@pytest.mark.parametrize("mode", ALL_MODES)
def test_invalid_new_file_names_can_be_corrected(pathfm, mode):
    name = "bad/name"
    field = start_new_file(pathfm)
    original = pathfm.fixture.names()
    pathfm.keyboard.type_text(name)
    pathfm.wait(lambda: field.text == name, "the invalid name to appear")
    pathfm.keyboard.press("Return")
    pathfm.wait(lambda: pathfm.window.find(role="text", name="Rename", states={"editable"}) is None, "the invalid edit to close")
    assert pathfm.fixture.names() == original
    pathfm.select_entry_with_keyboard("new file")
    pathfm.keyboard.press("F2")
    pathfm.editable_field()
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text("corrected")
    pathfm.keyboard.press("Return")
    pathfm.wait(lambda: pathfm.fixture.path("corrected").is_file(), "the corrected file on disk")
    pathfm.entry("corrected")


@pytest.mark.parametrize("kind", ["file", "folder"])
def test_clicking_inside_keeps_the_new_entry_and_preserves_its_name(pathfm, kind):
    name = " padded "
    if kind == "folder":
        pathfm.select_entry("readme.md")
        pathfm.keyboard.press("ctrl+shift+n")
        field = pathfm.editable_field()
    else:
        field = start_new_file(pathfm)
    pathfm.keyboard.type_text(name)
    pathfm.wait(lambda: field.text == name, "the name to appear")
    pathfm.pointer.click(field)
    pathfm.keyboard.press("Return")
    pathfm.wait(lambda: pathfm.fixture.path(name).exists(), "the exact name on disk")
    assert pathfm.fixture.path(name).is_dir() == (kind == "folder")
    pathfm.wait(
        lambda: pathfm.window.find(role="text", states={"editable"}) is None,
        "the submitted prompt to close",
    )


@pytest.mark.parametrize("kind,name", [("file", "todo.txt"), ("folder", "archive")])
@pytest.mark.usefixtures("unreserved_columns")
def test_creating_an_existing_name_does_not_overwrite(pathfm, kind, name):
    pathfm.select_entry("readme.md")
    if kind == "folder":
        pathfm.keyboard.press("ctrl+shift+n")
    else:
        pathfm.pointer.right_click(pathfm.pane(), at=pathfm.background_point())
        pathfm.choose_menu_item("New File")
    field = pathfm.editable_field()
    original = pathfm.fixture.listing()
    pathfm.keyboard.type_text(name)
    pathfm.wait(lambda: field.text == name, "the existing name to appear")
    pathfm.keyboard.press("Return")
    dialog = pathfm.wait_for_dialog()
    assert dialog.name == "Unable to rename item"
    pathfm.pointer.click(pathfm.dialog_button("Close"))
    pathfm.wait(lambda: pathfm.dialog() is None, "the error to be dismissible")
    pathfm.wait(
        lambda: pathfm.focused_pane() is not None or pathfm.focused_name() is not None,
        "focus returns to the listing",
    )
    assert pathfm.fixture.listing() == original
    assert pathfm.fixture.path("todo.txt").read_text() == "todo\n"
    root = pathfm.fixture.root.name
    pathfm.select_entry("readme.md", root)
    pathfm.wait_for_selection(["readme.md"], root)
    if kind == "folder":
        assert pathfm.pane_names() == [root, "new folder"]


@pytest.mark.parametrize("kind", ["file", "folder"])
def test_new_items_can_be_created_in_an_initially_empty_directory(pathfm, kind):
    pathfm.open_directory("archive")
    if kind == "folder":
        pathfm.keyboard.press("ctrl+shift+n")
        pathfm.editable_field()
    else:
        start_new_file(pathfm, select=False)
    pathfm.keyboard.type_text("discarded")
    pathfm.keyboard.press("Escape")
    pathfm.entry("new " + kind, directory="archive")
    if kind == "folder":
        pathfm.keyboard.press("ctrl+shift+n")
        field = pathfm.editable_field()
    else:
        field = start_new_file(pathfm, select=False)
    pathfm.keyboard.type_text("kept")
    pathfm.wait(lambda: field.text == "kept", "the replacement name to appear")
    pathfm.keyboard.press("Return")
    pathfm.wait(lambda: pathfm.fixture.path("archive/kept").exists(), "the renamed item on disk")
    assert pathfm.fixture.path("archive/kept").is_dir() == (kind == "folder")
    pathfm.entry("kept", directory="archive")
    assert not pathfm.fixture.path("archive/discarded").exists()
    assert "Gtk-CRITICAL" not in pathfm.application.log()


def test_undoing_a_created_folder_trashes_it(pathfm):
    fixture = pathfm.fixture
    trashed = pathfm.environment.trash_files

    pathfm.keyboard.press("ctrl+shift+n")
    pathfm.editable_field()
    pathfm.keyboard.press("Return")
    pathfm.wait(
        lambda: fixture.path("new folder").is_dir(),
        "the folder to be created",
    )
    pathfm.wait(
        lambda: pathfm.window.find(role="text", states={"editable"}) is None,
        "the name prompt to close",
    )

    pathfm.keyboard.press("ctrl+z")

    pathfm.wait(
        lambda: not fixture.path("new folder").exists(),
        "create undo to trash the folder",
    )
    pathfm.wait(
        lambda: any(trashed.iterdir()),
        "the folder to land in Trash",
    )


@pytest.mark.parametrize("shortcut", ["F2", "ctrl+r"])
def test_rename_shortcuts(pathfm, shortcut):
    fixture = pathfm.fixture

    pathfm.select_entry("todo.txt")
    pathfm.keyboard.press(shortcut)
    field = pathfm.editable_field()
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text("renamed.txt")
    pathfm.wait(lambda: field.text == "renamed.txt", "the new name to be typed")
    pathfm.keyboard.press("ctrl+r")
    assert pathfm.editable_field().text == "renamed.txt"
    pathfm.keyboard.press("Return")

    pathfm.wait(
        lambda: fixture.path("renamed.txt").exists(),
        "the file to be renamed on disk",
    )
    assert not fixture.path("todo.txt").exists()
    assert fixture.path("renamed.txt").read_text() == "todo\n"
    pathfm.entry("renamed.txt")


@pytest.mark.parametrize("shortcut", ["F2", "ctrl+r"])
def test_rename_shortcuts_leave_location_editing_alone(pathfm, shortcut):
    pathfm.select_entry("todo.txt")
    pathfm.keyboard.press("ctrl+l")
    field = pathfm.editable_field()
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text(str(pathfm.fixture.path("documents")))
    pathfm.wait(lambda: field.text.endswith("documents"), "the location to be typed")
    pathfm.keyboard.press(shortcut)
    assert pathfm.editable_field().text == str(pathfm.fixture.path("documents"))
    pathfm.keyboard.press("Return")
    pathfm.wait_for_directory("documents")
    assert pathfm.fixture.path("todo.txt").exists()


def test_rename_from_the_context_menu(pathfm):
    fixture = pathfm.fixture

    pathfm.open_context_menu("readme.md")
    pathfm.choose_menu_item("Rename")
    field = pathfm.editable_field()
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text("guide.md")
    pathfm.wait(lambda: field.text == "guide.md", "the new name to be typed")
    pathfm.keyboard.press("Return")

    pathfm.wait(lambda: fixture.path("guide.md").exists(), "the rename to apply")
    assert not fixture.path("readme.md").exists()


def test_delete_moves_the_entry_to_trash(pathfm):
    fixture = pathfm.fixture

    pathfm.select_entry("todo.txt")
    pathfm.keyboard.press("Delete")

    pathfm.wait(
        lambda: not fixture.path("todo.txt").exists(),
        "the file to leave the fixture tree",
    )
    pathfm.wait_for_entry_gone("todo.txt")
    trashed = pathfm.environment.trash_files
    assert trashed.exists() and any(trashed.iterdir()), (
        "the file should be recoverable from the isolated trash directory"
    )


@pytest.mark.preferences(browser_mode="columns", list_folder_clicks=1)
def test_trashing_an_open_folder_with_the_mouse_opens_the_folder_in_its_place(pathfm):
    """#1497: the mirror follows a deletion even when the pointer made it."""
    pathfm.fixture.populate({"aa-first": {"a.txt": "a\n"}, "aa-second": {"b.txt": "b\n"}})
    root = pathfm.fixture.root.name
    pathfm.pointer.click(pathfm.entry("aa-first"))
    pathfm.wait(lambda: pathfm.pane_names()[-1] == "aa-first", "the clicked folder to open")

    pathfm.open_context_menu("aa-first", root)
    pathfm.choose_menu_item("Move to Trash")

    pathfm.wait(lambda: not pathfm.fixture.path("aa-first").exists(), "the folder to move to the Trash")
    pathfm.wait(lambda: pathfm.pane_names()[-1] == "aa-second", "the folder now in its place to open")


@pytest.mark.parametrize("mode", COLUMNS_AND_ONE)
def test_permanent_delete_requires_confirmation_and_can_be_cancelled(pathfm, mode):
    fixture = pathfm.fixture
    assert pathfm.view_mode() == mode

    pathfm.select_entry("todo.txt")
    pathfm.keyboard.press("shift+Delete")

    dialog = pathfm.wait_for_dialog()
    assert dialog.role in ("dialog", "alert")
    assert dialog.name == "Permanently delete 1 item?", (
        f"unexpected dialog {dialog.name!r}"
    )
    assert fixture.path("todo.txt").exists(), (
        "nothing may be deleted before the confirmation is answered"
    )

    pathfm.pointer.click(pathfm.dialog_button("Cancel"))
    pathfm.wait(lambda: pathfm.dialog() is None, "the dialog to close")
    assert fixture.path("todo.txt").exists(), "cancelling must keep the file"

    pathfm.select_entry("todo.txt")
    pathfm.keyboard.press("shift+Delete")
    pathfm.wait_for_dialog()
    pathfm.pointer.click(pathfm.dialog_button("Permanently delete 1 item"))

    pathfm.wait(
        lambda: not fixture.path("todo.txt").exists(),
        "the file to be deleted",
    )
    pathfm.wait_for_entry_gone("todo.txt")
    trashed = pathfm.environment.trash_files
    assert not trashed.exists() or not any(trashed.iterdir()), (
        "a permanent delete must not go through the trash"
    )


@pytest.mark.parametrize("mode", COLUMNS_AND_ONE)
def test_permanent_delete_through_a_symlinked_parent(pathfm, mode):
    fixture = pathfm.fixture
    alias = fixture.path("documents-alias")
    alias.symlink_to(fixture.path("documents"), target_is_directory=True)

    pathfm.open_directory("documents-alias")
    pathfm.wait_for_directory("documents-alias")

    pathfm.select_entry("notes.txt", directory="documents-alias")
    pathfm.keyboard.press("shift+Delete")
    pathfm.wait_for_dialog()
    pathfm.pointer.click(pathfm.dialog_button("Permanently delete 1 item"))

    pathfm.wait(
        lambda: not fixture.path("documents/notes.txt").exists()
        or (pathfm.dialog() is not None and pathfm.dialog().name == "Completed with errors"),
        "the delete operation to finish",
    )
    assert not fixture.path("documents/notes.txt").exists()
    pathfm.wait_for_entry_gone("notes.txt", directory="documents-alias")
    pathfm.wait(lambda: pathfm.dialog() is None, "the confirmation dialog to close")
    assert alias.is_symlink()
    assert fixture.path("documents").is_dir()


@pytest.fixture
def trashless_volume(pathfm):
    with tempfile.TemporaryDirectory(prefix="pathfm-no-trash-", dir="/dev/shm") as directory:
        volume = Path(directory)
        assert volume.stat().st_dev != pathfm.fixture.path("todo.txt").stat().st_dev
        doomed = volume / "doomed.txt"
        doomed.write_text("doomed")
        info = Gio.File.new_for_path(str(doomed)).query_info(
            Gio.FILE_ATTRIBUTE_ACCESS_CAN_TRASH, Gio.FileQueryInfoFlags.NONE, None
        )
        assert info.get_attribute_boolean(Gio.FILE_ATTRIBUTE_ACCESS_CAN_TRASH) is False, (
            "precondition: /dev/shm must not support Trash (GIO refuses system-internal mounts)"
        )
        pathfm.fixture.path("no-trash").symlink_to(volume, target_is_directory=True)
        yield doomed


def explains_missing_trash(dialog):
    return dialog.find(
        predicate=lambda node: re.search(
            r"doesn't\s+support\s+Trash", f"{node.name} {node.text}"
        )
        is not None
    )


def confirm_without_trash_support(pathfm, doomed, key):
    dialog = pathfm.wait_for_dialog()
    assert dialog.name == "Permanently delete 1 item?", f"unexpected dialog {dialog.name!r}"
    pathfm.wait(lambda: explains_missing_trash(dialog), "the dialog to say Trash is unsupported")
    pathfm.wait(lambda: pathfm.dialog_button("Cancel").has_state("focused"), "Cancel focused")
    assert doomed.exists(), f"{key} must wait for confirmation"


@pytest.mark.parametrize("mode", COLUMNS_AND_ONE)
def test_delete_without_trash_support_explains_and_focuses_cancel(pathfm, trashless_volume, mode):
    assert pathfm.view_mode() == mode
    pathfm.open_directory("no-trash")
    pathfm.select_entry("doomed.txt", directory="no-trash")
    pathfm.keyboard.press("Delete")
    confirm_without_trash_support(pathfm, trashless_volume, "Delete")

    pathfm.keyboard.press("Return")
    pathfm.wait(lambda: pathfm.dialog() is None, "Enter on Cancel to close the dialog")
    assert trashless_volume.exists(), "Enter cancels"

    pathfm.select_entry("doomed.txt", directory="no-trash")
    pathfm.keyboard.press("Delete")
    pathfm.wait_for_dialog()
    pathfm.pointer.click(pathfm.dialog_button("Permanently delete 1 item"))
    pathfm.wait(lambda: not trashless_volume.exists(), "the file to be deleted")
    pathfm.wait_for_entry_gone("doomed.txt", directory="no-trash")
    trashed = pathfm.environment.trash_files
    assert not trashed.exists() or not any(trashed.iterdir()), (
        "a location without Trash must not reach the user's Trash"
    )


@pytest.mark.preferences(browser_mode="list", tenxer_mode=True, type_to_search=False)
def test_tenxer_d_without_trash_support_needs_an_explicit_confirmation(pathfm, trashless_volume):
    pathfm.select_entry_with_keyboard("no-trash")
    pathfm.keyboard.press("l")
    pathfm.wait_for_directory("no-trash")
    pathfm.select_entry_with_keyboard("doomed.txt")
    pathfm.keyboard.press("d")
    confirm_without_trash_support(pathfm, trashless_volume, "d")

    pathfm.keyboard.press("d")
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        assert pathfm.dialog() is not None and trashless_volume.exists(), "d never confirms it"
        time.sleep(0.05)
    pathfm.keyboard.press("Return")
    pathfm.wait(lambda: pathfm.dialog() is None, "Enter on Cancel to close the dialog")
    assert trashless_volume.exists(), "Enter cancels"


def test_undo_restores_a_completed_move(pathfm):
    fixture = pathfm.fixture

    pathfm.select_entry("todo.txt")
    pathfm.keyboard.press("ctrl+x")
    pathfm.open_directory("archive")
    pathfm.paste_into("archive")
    pathfm.wait(
        lambda: fixture.path("archive/todo.txt").exists(),
        "the move to complete",
    )

    pathfm.keyboard.press("ctrl+z")

    pathfm.wait(
        lambda: fixture.path("todo.txt").exists(),
        "undo to put the file back",
    )
    assert not fixture.path("archive/todo.txt").exists()


TENXER = pytest.mark.preferences(
    tenxer_mode=True,
    type_to_search=False,
    single_click_previews=False,
)


@TENXER
@pytest.mark.parametrize("mode", ALL_MODES)
def test_tenxer_footer_rename_keeps_contents_and_refuses_conflicts(pathfm, mode):
    fixture = pathfm.fixture
    root = fixture.root.name
    pathfm.select_entry_with_keyboard("todo.txt")

    pathfm.keyboard.press("r")
    field = pathfm.editable_field()
    pathfm.wait(lambda: field.text == "todo.txt", "r to fill in the focused name")
    pathfm.keyboard.type_text("discarded")
    pathfm.keyboard.press("Escape")
    pathfm.wait(lambda: pathfm.window.find(role="text", states={"editable", "focused"}) is None, "Esc to close the prompt")
    pathfm.wait_for_focused_entry("todo.txt")

    pathfm.keyboard.press("F2")
    field = pathfm.editable_field()
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text("readme.md")
    pathfm.keyboard.press("Return")
    pathfm.wait(
        lambda: pathfm.window.find(role="label", name="“readme.md” already exists") is not None,
        "the conflict to keep the prompt open with its reason",
    )
    assert field.has_state("focused")
    assert fixture.path("readme.md").read_text() == "# Fixture\n"

    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text("done list.txt")
    pathfm.keyboard.press("Return")
    pathfm.wait(lambda: fixture.path("done list.txt").is_file(), "Enter to rename the file")
    assert fixture.path("done list.txt").read_text() == "todo\n"
    assert not fixture.path("todo.txt").exists()
    pathfm.wait_for_focused_entry("done list.txt")

    pathfm.keyboard.press("r")
    pathfm.editable_field()
    pathfm.keyboard.type_text("clicked")
    pathfm.click_entry("readme.md", root)
    pathfm.wait(lambda: pathfm.window.find(role="text", states={"editable", "focused"}) is None, "a click to end the prompt")
    pathfm.wait_for_selection(["readme.md"], root)
    assert fixture.path("done list.txt").is_file()
    assert not any("clicked" in name for name in fixture.names())


@pytest.mark.parametrize("mode", ALL_MODES)
@pytest.mark.usefixtures("unreserved_columns")
def test_new_folder_with_selection_groups_items_and_names_it(pathfm, mode):
    fixture = pathfm.fixture
    root = fixture.root.name

    pathfm.select_entry("readme.md", root)
    pathfm.click_entry_with("todo.txt", ["ctrl"], directory=root)
    pathfm.wait_for_selection(["readme.md", "todo.txt"], root)
    pathfm.pointer.right_click(pathfm.entry("readme.md", root))
    pathfm.wait(pathfm.context_menu, "the selection context menu")
    pathfm.choose_menu_item("New Folder with Selection")

    field = pathfm.editable_field()
    pathfm.wait(lambda: field.text.startswith("new folder"), "the new folder's editor")
    pathfm.keyboard.type_text("grouped")
    pathfm.keyboard.press("Return")
    pathfm.wait(
        lambda: fixture.path("grouped/readme.md").is_file(),
        "the selection moved into the named folder",
    )
    assert fixture.path("grouped/todo.txt").is_file()
    assert not fixture.path("readme.md").exists()
    assert not fixture.path("todo.txt").exists()
    # The parent row's name is optimistic; the renamed child listing follows completion.
    if mode == "Columns":
        pathfm.entry("readme.md", "grouped")
        pathfm.entry("todo.txt", "grouped")
    pathfm.wait(
        lambda: pathfm.window.find(role="text", states={"editable", "focused"}) is None,
        "the rename editor to release keyboard focus",
    )
    pathfm.click_entry("grouped", root)
    if mode == "Columns":
        # Clicking the open folder focuses its column; return to the parent.
        pathfm.wait(
            lambda: (pane := pathfm.focused_pane()) is not None and pane.name == "grouped",
            "the open folder's column to take focus",
        )
        pathfm.keyboard.press("Left")
    pathfm.select_entry_with_keyboard("grouped")

    pathfm.keyboard.press("ctrl+z")
    pathfm.wait(
        lambda: fixture.path("readme.md").is_file()
        and fixture.path("todo.txt").is_file()
        and not fixture.path("grouped").exists()
        and not fixture.path("new folder").exists(),
        "the gesture undone",
    )
    pathfm.entry("readme.md", root)
