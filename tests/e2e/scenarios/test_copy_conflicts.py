# SPDX-License-Identifier: MIT

import pytest


@pytest.mark.parametrize("activation", ["pointer", "Return"])
def test_keep_both_selects_the_numbered_copy_and_undo_preserves_originals(pathfm, activation):
    fixture = pathfm.fixture
    fixture.path("archive/todo.txt").write_text("existing\n")
    fixture.path("archive/todo (1).txt").write_text("previous copy\n")
    pathfm.select_entry("todo.txt")
    pathfm.keyboard.press("ctrl+c")
    pathfm.open_directory("archive")
    pathfm.paste_into("archive")
    pathfm.wait_for_dialog()

    if activation == "pointer":
        pathfm.pointer.click(pathfm.dialog_button("Keep Both"))
    else:
        pathfm.wait(
            lambda: pathfm.dialog_button("Replace").has_state("focused"),
            "Replace to receive initial focus",
        )
        pathfm.keyboard.press("shift+Tab")
        pathfm.wait(
            lambda: pathfm.dialog_button("Keep Both").has_state("focused"),
            "Keep Both to receive keyboard focus",
        )
        pathfm.keyboard.press("Return")

    pathfm.wait(lambda: fixture.path("archive/todo (2).txt").exists(), "the numbered copy")
    pathfm.wait(
        lambda: pathfm.selected_names("archive") == ["todo (2).txt"],
        "the numbered copy to be selected",
    )
    assert fixture.path("archive/todo (2).txt").read_text() == "todo\n"
    # The copy can finish while the dismissing modal still owns keyboard input.
    pathfm.wait(lambda: pathfm.dialog() is None, "the conflict dialog to finish dismissing")
    pathfm.wait_for_focused_entry("todo (2).txt")
    pathfm.keyboard.press("ctrl+z")
    pathfm.wait(lambda: not fixture.path("archive/todo (2).txt").exists(), "copy undo")
    assert fixture.path("todo.txt").read_text() == "todo\n"
    assert fixture.path("archive/todo.txt").read_text() == "existing\n"
    assert fixture.path("archive/todo (1).txt").read_text() == "previous copy\n"


@pytest.mark.parametrize(
    "moving,action",
    [
        (False, "Cancel"),
        (False, "Escape"),
        (False, "Close dialog"),
        (True, "Cancel"),
    ],
    ids=["copy-Cancel", "copy-Escape", "copy-Close", "move-Cancel"],
)
def test_dismissing_a_copy_or_move_conflict_preserves_both_files(pathfm, moving, action):
    fixture = pathfm.fixture
    fixture.path("archive/todo.txt").write_text("existing\n")
    pathfm.select_entry("todo.txt")
    pathfm.keyboard.press("ctrl+x" if moving else "ctrl+c")
    pathfm.open_directory("archive")
    pathfm.paste_into("archive")
    dialog = pathfm.wait_for_dialog()
    assert (dialog.find(role="button", name="Keep Both") is not None) == (not moving)
    assert dialog.find(role="button", name="Merge") is None, (
        "a file collision cannot merge"
    )

    if action == "Escape":
        pathfm.keyboard.press("Escape")
    else:
        pathfm.pointer.click(pathfm.dialog_button(action))
    pathfm.wait(lambda: pathfm.dialog() is None, "the conflict dialog to close")
    assert fixture.path("todo.txt").read_text() == "todo\n"
    assert fixture.path("archive/todo.txt").read_text() == "existing\n"
    assert not fixture.path("archive/todo (1).txt").exists()


def test_keep_both_applies_to_all_collisions_in_a_mixed_paste(pathfm):
    fixture = pathfm.fixture
    for name in ["notes.txt", "report.md"]:
        fixture.path(f"archive/{name}").write_text(f"existing {name}\n")
    pathfm.open_directory("documents")
    pathfm.select_entry_with_keyboard("notes.txt")
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.press("ctrl+c")
    pathfm.keyboard.press("alt+Up")
    pathfm.wait_for_directory(fixture.root.name)
    pathfm.open_directory("archive")
    pathfm.paste_into("archive")
    dialog = pathfm.wait_for_dialog()
    apply_all = dialog.find(name="Apply to All")
    assert apply_all is not None, dialog.dump()
    pathfm.pointer.click(apply_all)
    pathfm.pointer.click(pathfm.dialog_button("Keep Both"))
    pathfm.wait(
        lambda: all(
            fixture.path(f"archive/{name}").exists()
            for name in ["notes (1).txt", "report (1).md", "spreadsheet.csv"]
        ),
        "all mixed-paste copies",
    )
    for name, copied in [
        ("notes.txt", "notes (1).txt"),
        ("report.md", "report (1).md"),
        ("spreadsheet.csv", "spreadsheet.csv"),
    ]:
        assert fixture.path(f"archive/{copied}").read_bytes() == fixture.path(
            f"documents/{name}"
        ).read_bytes()
    for name in ["notes.txt", "report.md"]:
        assert fixture.path(f"archive/{name}").read_text() == f"existing {name}\n"


def test_merge_combines_folder_contents(pathfm):
    fixture = pathfm.fixture
    fixture.path("folder").mkdir()
    fixture.path("folder/incoming.txt").write_text("from source\n")
    fixture.path("folder/shared.txt").write_text("incoming\n")
    fixture.path("archive/folder").mkdir()
    fixture.path("archive/folder/stays.txt").write_text("kept\n")
    fixture.path("archive/folder/shared.txt").write_text("original\n")
    pathfm.open_context_menu("folder")
    pathfm.choose_menu_item("Copy")
    pathfm.open_directory("archive")
    pathfm.paste_into("archive")

    pathfm.wait_for_dialog()
    pathfm.pointer.click(pathfm.dialog_button("Merge"))

    # The overwritten original is staged in Trash before the incoming copy
    # lands, so a bare existence check can catch the file mid-staging.
    pathfm.wait(
        lambda: fixture.path("archive/folder/incoming.txt").exists()
        and fixture.path("archive/folder/shared.txt").exists(),
        "the merged incoming files",
    )
    pathfm.wait(
        lambda: fixture.path("archive/folder/shared.txt").read_text() == "incoming\n",
        "the incoming item to overwrite a same-named destination item",
    )
    assert fixture.path("archive/folder/stays.txt").read_text() == "kept\n", (
        "destination-only contents survive the merge"
    )
    assert fixture.path("folder/incoming.txt").exists(), "a copy merge keeps the source"

    pathfm.wait(lambda: pathfm.dialog() is None, "the conflict dialog to finish dismissing")
    pathfm.keyboard.press("ctrl+z")
    pathfm.wait(
        lambda: not fixture.path("archive/folder/incoming.txt").exists(),
        "merge undo removes the created file",
    )
    assert fixture.path("archive/folder/shared.txt").read_text() == "original\n", (
        "merge undo restores the overwritten original from Trash"
    )
    assert fixture.path("archive/folder/stays.txt").read_text() == "kept\n", (
        "merge undo leaves destination-only contents alone"
    )
    assert fixture.path("archive/folder").is_dir(), "the destination folder survives undo"
    assert fixture.path("folder/incoming.txt").exists(), "the source is still intact"


def test_replacing_a_file_restores_the_original_on_undo(pathfm):
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
        "the replacement",
    )
    assert fixture.path("todo.txt").read_text() == "todo\n", "a copy keeps the source"

    pathfm.wait(lambda: pathfm.dialog() is None, "the conflict dialog to finish dismissing")
    pathfm.keyboard.press("ctrl+z")
    pathfm.wait(
        lambda: fixture.path("archive/todo.txt").read_text() == "existing\n",
        "replace undo restores the original staged in Trash",
    )
    assert fixture.path("todo.txt").read_text() == "todo\n"
