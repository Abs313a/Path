# SPDX-License-Identifier: MIT
import pytest


@pytest.mark.preferences(browser_mode="columns", single_click_previews=False)
@pytest.mark.parametrize("surface", ["item", "background"])
@pytest.mark.parametrize("previous", ["root", "nested"])
@pytest.mark.usefixtures("unreserved_columns")
def test_context_menu_keeps_the_clicked_column_target(pathfm, surface, previous):
    root = pathfm.fixture.root.name
    nested = pathfm.fixture.path("documents/nested")
    nested.mkdir()
    (nested / "child.txt").write_text("child")
    pathfm.open_directory("documents")
    pathfm.open_directory("nested", directory="documents")
    previous_directory = root if previous == "root" else "nested"
    pathfm.select_entry(
        "readme.md" if previous == "root" else "child.txt",
        directory=previous_directory,
    )
    if surface == "item":
        pathfm.open_context_menu("notes.txt", directory="documents")
    else:
        pathfm.pointer.click(
            pathfm.pane("documents"),
            at=pathfm.background_point("documents"),
            button=3,
        )
        pathfm.wait(pathfm.context_menu, "the background context menu to open")

    def action_owners():
        return [name for name in pathfm.pane_names()
                if pathfm.pane(name).find(role="button", name="Refresh (F5)") is not None]

    pathfm.wait(lambda: action_owners() == ["documents"], "actions to stay on the menu's column")
    pathfm.pointer.move_to(*pathfm.pane(previous_directory).screen_bounds().center)
    assert pathfm.context_menu() is not None
    assert action_owners() == ["documents"]
    pathfm.keyboard.press("Escape")
    pathfm.wait(lambda: pathfm.context_menu() is None, "the context menu to close")
    pathfm.keyboard.press("Down")
    pathfm.wait_for_focused_entry("report.md" if surface == "item" else "notes.txt")
    pathfm.wait(lambda: action_owners() == ["documents"], "keyboard navigation to resume in the menu's column")


@pytest.mark.preferences(browser_mode="columns")
@pytest.mark.parametrize("surface", ["content", "header"])
@pytest.mark.usefixtures("unreserved_columns")
def test_column_background_click_focuses_parent(pathfm, surface):
    root = pathfm.fixture.root.name
    pathfm.open_directory("documents")
    selected = pathfm.selected_names(directory=root)
    if surface == "content":
        pathfm.pointer.click(pathfm.pane(root), at=pathfm.background_point(root))
    else:
        heading = pathfm.window.find(
            role="label", name=root, description=str(pathfm.fixture.root)
        )
        assert heading is not None
        pathfm.pointer.click(heading)
    pathfm.wait_for_directory(root)
    if surface == "content":
        pathfm.wait_for_selection(["archive"], root)
        pathfm.pointer.click(pathfm.pane(root), at=pathfm.background_point(root))
        pathfm.wait(lambda: not pathfm.all_selected_names(), "active background click to clear selection")
        assert "documents" not in pathfm.pane_names()
    else:
        assert pathfm.selected_names(directory=root) == selected
        # The header label is chrome, not content background: it only focuses.
        assert "documents" in pathfm.pane_names()
