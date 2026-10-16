# SPDX-License-Identifier: MIT

import tarfile
import zipfile

import pytest

from harness.modes import ALL_MODES


@pytest.fixture
def fixture_tree(fixture_tree, request):
    extension = request.node.callspec.params.get("extension", "zip")
    fixture_tree.path(f"archive.{extension}").write_bytes(b"original archive")
    fixture_tree.path(f"archive (1).{extension}").write_bytes(b"previous archive")
    return fixture_tree


def request_archive_collision(pathfm, format="ZIP"):
    pathfm.select_entry("todo.txt")
    pathfm.open_context_menu("todo.txt")
    pathfm.choose_menu_item("Compress…")
    dialog = pathfm.wait_for_dialog()
    field = pathfm.editable_field()
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text("archive")
    pathfm.wait(lambda: field.text == "archive", "archive name input")
    format_button = dialog.find(role="toggle button", name=format)
    pathfm.pointer.click(format_button)
    pathfm.wait(lambda: format_button.has_state("pressed"), "selected archive format")
    assert pathfm.dialog_button("Compress").activate()
    pathfm.wait(
        lambda: (dialog := pathfm.dialog()) is not None and dialog.name == "File already exists",
        "archive collision prompt",
    )


@pytest.mark.parametrize("mode", ALL_MODES)
@pytest.mark.parametrize("format,extension", [("ZIP", "zip"), ("TAR.GZ", "tar.gz")])
@pytest.mark.parametrize("activation", ["pointer", "Return"])
def test_keep_both_preserves_archives_and_selects_each_numbered_output(pathfm, mode, format, extension, activation):
    fixture = pathfm.fixture
    original = fixture.path(f"archive.{extension}")
    previous = fixture.path(f"archive (1).{extension}")
    for suffix in [2, 3]:
        request_archive_collision(pathfm, format)
        if activation == "pointer":
            pathfm.pointer.click(pathfm.dialog_button("Keep Both"))
        else:
            pathfm.wait(lambda: pathfm.dialog_button("Replace").has_state("focused"), "initial Replace focus")
            pathfm.keyboard.press("shift+Tab")
            pathfm.wait(lambda: pathfm.dialog_button("Keep Both").has_state("focused"), "Keep Both focus")
            pathfm.keyboard.press("Return")
        name = f"archive ({suffix}).{extension}"
        path = fixture.path(name)
        pathfm.wait(path.exists, "numbered archive publication")
        pathfm.wait(lambda: pathfm.dialog() is None, "archive progress dismissal")
        pathfm.wait_for_selection([name])
        pathfm.wait(lambda: pathfm.on_screen(pathfm.entry(name)), "numbered archive reveal")
        if format == "ZIP":
            with zipfile.ZipFile(path) as archive:
                assert archive.namelist() == ["todo.txt"]
                assert archive.read("todo.txt") == fixture.path("todo.txt").read_bytes()
        else:
            with tarfile.open(path, "r:gz") as archive:
                assert archive.getnames() == ["todo.txt"]
                assert archive.extractfile("todo.txt").read() == fixture.path("todo.txt").read_bytes()
        assert original.read_bytes() == b"original archive"
        assert previous.read_bytes() == b"previous archive"


@pytest.mark.parametrize("extension", ["zip"])
def test_undoing_a_compression_trashes_the_numbered_archive(pathfm, extension):
    fixture = pathfm.fixture
    trashed = pathfm.environment.trash_files

    request_archive_collision(pathfm)
    pathfm.pointer.click(pathfm.dialog_button("Keep Both"))
    numbered = fixture.path(f"archive (2).{extension}")
    pathfm.wait(numbered.exists, "numbered archive publication")
    pathfm.wait(lambda: pathfm.dialog() is None, "archive progress dismissal")

    pathfm.keyboard.press("ctrl+z")

    pathfm.wait(lambda: not numbered.exists(), "compress undo to trash the archive")
    pathfm.wait(lambda: any(trashed.iterdir()), "the archive to land in Trash")
    assert fixture.path(f"archive.{extension}").read_bytes() == b"original archive"
    assert fixture.path(f"archive (1).{extension}").read_bytes() == b"previous archive"


@pytest.mark.parametrize("choice", ["Cancel", "Escape", "Replace"])
def test_archive_conflict_keyboard_choices_preserve_cancel_and_replace_behavior(pathfm, choice):
    original = pathfm.fixture.path("archive.zip")
    if choice == "Replace":
        older = pathfm.environment.trash_files / "older-archive.zip"
        older.parent.mkdir(parents=True, exist_ok=True)
        older.write_bytes(b"older trashed archive")
        trash_info = pathfm.environment.data_home / "Trash" / "info"
        trash_info.mkdir(parents=True, exist_ok=True)
        encoded_path = original.as_uri().removeprefix("file://")
        (trash_info / "older-archive.zip.trashinfo").write_text(
            f"[Trash Info]\nPath={encoded_path}\nDeletionDate=2026-01-01T00:00:00\n"
        )
    request_archive_collision(pathfm)
    pathfm.wait(lambda: pathfm.dialog_button("Replace").has_state("focused"), "initial Replace focus")
    if choice == "Escape":
        pathfm.keyboard.press("Escape")
    else:
        if choice == "Cancel":
            pathfm.keyboard.press("shift+Tab")
            pathfm.keyboard.press("shift+Tab")
            pathfm.wait(lambda: pathfm.dialog_button("Cancel").has_state("focused"), "Cancel focus")
        pathfm.keyboard.press("Return")
    pathfm.wait(lambda: pathfm.dialog() is None, "conflict dismissal")
    if choice in {"Cancel", "Escape"}:
        pathfm.wait_for_focused_entry("todo.txt")
    assert pathfm.fixture.path("archive (1).zip").read_bytes() == b"previous archive"
    assert not pathfm.fixture.path("archive (2).zip").exists()
    if choice == "Replace":
        pathfm.wait(lambda: zipfile.is_zipfile(original), "replacement archive publication")
        with zipfile.ZipFile(original) as archive:
            assert archive.namelist() == ["todo.txt"]
            assert archive.read("todo.txt") == pathfm.fixture.path("todo.txt").read_bytes()
        pathfm.wait(lambda: pathfm.dialog() is None, "archive progress dismissal")
        # Equal deletion timestamps must not redirect undo to the older entry.
        for info in trash_info.glob("*.trashinfo"):
            lines = info.read_text().splitlines()
            info.write_text("\n".join(
                "DeletionDate=2026-01-01T00:00:00" if line.startswith("DeletionDate=") else line
                for line in lines
            ) + "\n")
        pathfm.keyboard.press("ctrl+z")
        pathfm.wait(
            lambda: original.exists() and original.read_bytes() == b"original archive",
            "compression undo to restore the replaced archive",
        )
        assert pathfm.fixture.path("archive (1).zip").read_bytes() == b"previous archive"
        assert older.read_bytes() == b"older trashed archive"
    else:
        assert original.read_bytes() == b"original archive"
