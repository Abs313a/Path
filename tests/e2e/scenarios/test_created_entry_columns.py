# SPDX-License-Identifier: MIT
"""Creation keeps the Miller path, selection, and real keyboard focus consistent."""

import pytest


def create_in_parent(pathfm, kind, stale_child):
    root = pathfm.fixture.root.name
    if stale_child:
        pathfm.open_directory("documents")
    pathfm.pointer.right_click(pathfm.pane(root), at=pathfm.background_point(root))
    pathfm.choose_menu_item("New Folder" if kind == "folder" else "New File")
    field = pathfm.wait(
        lambda: pathfm.window.find(role="text", name="Rename", states={"editable", "focused"}),
        "the parent rename editor to take keyboard focus",
    )
    original = "new " + kind
    pathfm.wait(lambda: field.text == original, "the default name")
    path = pathfm.fixture.path(original)
    assert path.is_dir() if kind == "folder" else path.is_file()
    pathfm.wait_for_selection([original], root)
    expected = [root, original] if kind == "folder" else [root]
    pathfm.wait(lambda: pathfm.pane_names() == expected, "the child path to follow creation")
    assert pathfm.current_directory() == root
    return field, original


@pytest.mark.preferences(browser_mode="columns", single_click_previews=False)
def test_created_folder_editor_stays_visible_in_a_narrow_window(pathfm):
    pathfm.select_entry("readme.md")
    bounds = pathfm.window.window_bounds()
    pathfm.keyboard.connection.resize_surface(bounds.width, bounds.height, 420, 300)
    pathfm.wait(lambda: pathfm.window.window_bounds().width == 420, "a narrow window")
    pathfm.keyboard.press("ctrl+shift+n")
    field = pathfm.wait(
        lambda: pathfm.window.find(role="text", name="Rename", states={"editable", "focused"}),
        "the new folder editor to remain visible in the parent",
    )
    pathfm.keyboard.type_text("visible-folder")
    pathfm.wait(lambda: field.text == "visible-folder", "typing in the visible editor")
    editor = field.window_bounds()
    root = pathfm.pane(pathfm.fixture.root.name).window_bounds()
    assert editor.width > 1 and editor.x >= max(root.x, 0)
    assert editor.x + editor.width <= pathfm.window.window_bounds().width
    pathfm.keyboard.press("Return")
    pathfm.wait(pathfm.fixture.path("visible-folder").is_dir, "the visible folder rename")


@pytest.mark.preferences(browser_mode="columns", single_click_previews=False)
@pytest.mark.parametrize("kind", ["file", "folder"])
@pytest.mark.parametrize("stale_child", [False, True], ids=["no-child", "stale-child"])
@pytest.mark.parametrize("completion", ["enter", "sibling", "navigate"])
@pytest.mark.usefixtures("unreserved_columns")
def test_created_entry_completion_preserves_the_users_focus(pathfm, kind, stale_child, completion):
    root = pathfm.fixture.root.name
    field, original = create_in_parent(pathfm, kind, stale_child)
    pathfm.keyboard.type_text("renamed")
    pathfm.wait(lambda: field.text == "renamed", "typing to replace the entire default name")
    if completion == "enter":
        pathfm.keyboard.press("Return")
    elif completion == "sibling":
        pathfm.pointer.click(pathfm.entry("readme.md", root))
    else:
        pathfm.pointer.click(pathfm.sidebar_button("Home"))
    pathfm.wait(pathfm.fixture.path("renamed").exists, "the rename on disk")
    pathfm.wait(
        lambda: pathfm.window.find(role="text", name="Rename", states={"editable"}) is None,
        "the editor to close",
    )
    assert not pathfm.fixture.path(original).exists()
    if completion == "navigate":
        pathfm.wait_for_directory(pathfm.environment.home.name)
        assert root not in pathfm.pane_names()
    else:
        expected = [root, "renamed"] if kind == "folder" else [root]
        pathfm.wait(lambda: pathfm.pane_names() == expected, "the renamed child header")
        selected = "renamed" if completion == "enter" else "readme.md"
        pathfm.wait_for_selection([selected], root)
        pathfm.wait_for_directory(root)
        # No pointer correction: F2 must use the item selected by the previous action.
        pathfm.keyboard.press("F2")
        reopened = pathfm.wait(
            lambda: pathfm.window.find(role="text", name="Rename", states={"editable", "focused"}),
            "F2 to rename the still-selected parent item",
        )
        assert reopened.text == selected
        pathfm.keyboard.press("Escape")
    assert pathfm.window.find(role="dialog") is None
    assert "Gtk-CRITICAL" not in pathfm.application.log()
