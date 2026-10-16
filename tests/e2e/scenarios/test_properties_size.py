# SPDX-License-Identifier: MIT
"""Properties measures directory contents rather than directory metadata."""

import pytest


def _measurement_finished(dialog):
    spinner = dialog.find(name="Calculating folder size")
    return spinner is None or not spinner.is_rendered()


@pytest.fixture
def sized_folder(fixture_tree):
    fixture_tree.populate(
        {
            "sized-folder": {
                "top.txt": "abc",
                "nested": {"child.txt": "12345", ".hidden.txt": "1234567"},
                ".hidden": {"visible": {"file.txt": "123"}},
            }
        }
    )
    folder = fixture_tree.path("sized-folder")
    (folder / "nested/loop").symlink_to(folder, target_is_directory=True)
    (folder / "outside").symlink_to(fixture_tree.path("todo.txt"))
    return folder


@pytest.mark.parametrize("current_folder", [False, True], ids=["entry", "current-folder"])
def test_properties_calculates_nested_and_hidden_file_sizes(
    sized_folder, pathfm, current_folder
):
    if current_folder:
        pathfm.open_directory(sized_folder.name)
        pathfm.pointer.right_click(pathfm.pane(), at=pathfm.background_point())
        pathfm.wait(pathfm.context_menu, "the folder context menu")
    else:
        pathfm.open_context_menu(sized_folder.name)
    pathfm.choose_menu_item("Properties")
    dialog = pathfm.wait_for_dialog()

    pathfm.wait(
        lambda: dialog.find(role="label", name="18 B"),
        "Properties to show the recursive size without following symlinks",
    )
    pathfm.wait(lambda: _measurement_finished(dialog), "the size spinner to disappear")
    assert dialog.find(role="label", name="4 files, 1 folder")


def test_properties_explains_unreadable_folder_contents(sized_folder, pathfm):
    blocked = sized_folder / ".hidden"
    blocked.chmod(0)
    try:
        pathfm.open_context_menu(sized_folder.name)
        pathfm.choose_menu_item("Properties")
        dialog = pathfm.wait_for_dialog()
        pathfm.wait(lambda: _measurement_finished(dialog), "the measurement to finish")
        assert dialog.find(role="label", name="≥ 15 B")
        assert dialog.find(role="label", name="≥ 4 files, ≥ 1 folder")
        message = "Totals are incomplete.\nSome folders or entries couldn't be read."
        warning = pathfm.wait(lambda: dialog.find(name=message), "the incomplete measurement warning")
        assert warning.is_rendered()
    finally:
        blocked.chmod(0o755)


@pytest.mark.parametrize("route", ["keyboard", "context-menu"])
@pytest.mark.parametrize("unreadable", [False, True])
@pytest.mark.usefixtures("unreserved_columns")
def test_selection_properties_routes_preserve_aggregate_warnings(
    sized_folder, pathfm, route, unreadable
):
    blocked = sized_folder / ".hidden"
    if unreadable:
        blocked.chmod(0)
    try:
        pathfm.select_entry("sized-folder")
        pathfm.pointer.click(pathfm.entry("readme.md"), modifiers=["ctrl"])
        pathfm.wait_for_selection(["sized-folder", "readme.md"], sized_folder.parent.name)
        if route == "keyboard":
            pathfm.keyboard.press("alt+Return")
        else:
            pathfm.open_context_menu("readme.md", sized_folder.parent.name)
            pathfm.choose_menu_item("Properties")
        dialog = pathfm.wait_for_dialog()
        expected = "≥ 25 B" if unreadable else "28 B"
        pathfm.wait(
            lambda: dialog.find(role="label", name=expected),
            "the combined selection size",
        )
        counts = "≥ 5 files, ≥ 1 folder" if unreadable else "5 files, 1 folder"
        assert dialog.find(role="label", name=counts)
        if unreadable:
            warning = dialog.find(
                name="Totals are incomplete.\nSome folders or entries couldn't be read."
            )
            assert warning and warning.is_rendered()
    finally:
        blocked.chmod(0o755)


@pytest.mark.parametrize("name, expected", [("archive", "0 B"), ("readme.md", "10 B")])
def test_properties_shows_zero_for_empty_folders_and_preserves_file_sizes(
    pathfm, name, expected
):
    pathfm.open_context_menu(name)
    pathfm.choose_menu_item("Properties")
    dialog = pathfm.wait_for_dialog()

    pathfm.wait(
        lambda: dialog.find(role="label", name=expected),
        f"Properties to show {expected}",
    )
    pathfm.wait(lambda: _measurement_finished(dialog), "no spinner after measurement")
