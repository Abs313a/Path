# SPDX-License-Identifier: GPL-3.0-or-later
"""Inline editors and committed names stay inside their listing viewport."""

import pytest


def wait_for_visible_commit(pathfm, name):
    def visible():
        pane = pathfm.pane("rename-target")
        entry = pane.find(role="list item", name=name)
        if entry is None or not entry.has_state("selected"):
            return False
        panel = entry.find(role="panel")
        if panel is None:
            return False
        bounds = panel.screen_bounds()
        viewport = pathfm.entry_container("rename-target").screen_bounds()
        return (
            bounds.width > 0 and bounds.height > 0
            and bounds.x >= viewport.x and bounds.y >= viewport.y
            and bounds.x + bounds.width <= viewport.x + viewport.width
            and bounds.y + bounds.height <= viewport.y + viewport.height
        )

    pathfm.wait(visible, f"{name} selected and fully inside the viewport")
    pathfm.settle(pathfm.entry(name, "rename-target").find(role="panel"))
    assert visible()


def begin_long_directory_rename(pathfm, kind, new, mode="Columns"):
    pathfm.switch_view(mode)
    pathfm.fixture.path("rename-target").mkdir()
    for index in range(80):
        path = pathfm.fixture.path(f"rename-target/m-entry-{index:03d}")
        if kind == "folder":
            path.mkdir()
            (path / "marker").write_text("body\n")
        else:
            path.write_text("body\n")
    pathfm.keyboard.press("F5")
    pathfm.entry("rename-target")
    pathfm.open_directory("rename-target")
    pathfm.keyboard.press("Home")
    pathfm.keyboard.press("End")
    original = "m-entry-079"
    pathfm.wait_for_selection([original], "rename-target")
    if new:
        # Aim creation at the parent, not the selected folder's child column.
        bounds = pathfm.entry_container("rename-target").screen_bounds()
        pathfm.pointer.right_click(
            pathfm.pane("rename-target"),
            at=(bounds.x + 1, bounds.y + bounds.height // 2),
        )
        pathfm.choose_menu_item("New File" if kind == "file" else "New Folder")
        original = "new " + kind
        pathfm.wait(
            pathfm.fixture.path("rename-target/" + original).exists,
            "the new item on disk",
        )
    else:
        pathfm.keyboard.press("F2")
    field = pathfm.editable_field()
    pathfm.wait(lambda: field.text == original, "the original name in the editor")
    def editor_visible():
        viewport = pathfm.entry_container("rename-target").screen_bounds()
        bounds = field.screen_bounds()
        return (bounds.height > 0 and bounds.width > 0
                and bounds.y >= viewport.y
                and bounds.y + bounds.height <= viewport.y + viewport.height)

    pathfm.wait(editor_visible, "the initial editor inside the viewport without scrolling")
    pathfm.settle(field)
    assert editor_visible()
    path = pathfm.fixture.path("rename-target/" + original)
    assert path.is_dir() if kind == "folder" else path.is_file()
    return field, original


@pytest.mark.parametrize("new", (False, True), ids=("existing", "new"))
@pytest.mark.parametrize("final_name", ("a-final", "m-entry-078a", "zz-final"))
@pytest.mark.parametrize("mode", ("Columns", "List"))
def test_committed_rename_visibility(pathfm, new, final_name, mode):
    field, original = begin_long_directory_rename(pathfm, "file", new, mode)
    pathfm.keyboard.type_text(final_name)
    pathfm.wait(lambda: field.text == final_name, "the committed name in the editor")
    pathfm.keyboard.press("Return")
    destination = pathfm.fixture.path("rename-target/" + final_name)
    pathfm.wait(destination.exists, "the renamed item on disk")
    pathfm.wait_for_entry_gone(original, "rename-target")
    assert destination.read_text() == ("" if new else "body\n")
    assert not pathfm.fixture.path("rename-target/" + original).exists()
    wait_for_visible_commit(pathfm, final_name)
    names = sorted(path.name for path in pathfm.fixture.path("rename-target").iterdir())
    position = names.index(final_name)
    key, neighbor = ("Down", names[position + 1]) if position == 0 else ("Up", names[position - 1])
    pathfm.keyboard.press(key)
    pathfm.wait_for_selection([neighbor], "rename-target")
    pathfm.keyboard.press("Up" if key == "Down" else "Down")
    pathfm.wait_for_selection([final_name], "rename-target")
    wait_for_visible_commit(pathfm, final_name)


@pytest.mark.preferences(browser_density="airy")
@pytest.mark.parametrize("mode", ("Columns", "List"))
def test_airy_committed_rename_stays_visible(pathfm, mode):
    field, original = begin_long_directory_rename(pathfm, "file", False, mode)
    final_name = "zz-airy-final"
    pathfm.keyboard.type_text(final_name)
    pathfm.wait(lambda: field.text == final_name, "the committed name in the editor")
    pathfm.keyboard.press("Return")
    pathfm.wait(
        pathfm.fixture.path("rename-target/" + final_name).exists,
        "the renamed item on disk",
    )
    pathfm.wait_for_entry_gone(original, "rename-target")
    wait_for_visible_commit(pathfm, final_name)


@pytest.mark.preferences(single_click_previews=False)
@pytest.mark.parametrize("mode", ("Columns", "List"))
def test_already_visible_rename_preserves_scroll(pathfm, mode):
    begin_long_directory_rename(pathfm, "file", False, mode)
    pathfm.keyboard.press("Escape")
    for _ in range(8):
        pathfm.keyboard.press("Up")
    original = "m-entry-071"
    final_name = original + "a"
    pathfm.wait_for_selection([original], "rename-target")
    # A preceding row is unaffected by the editor's temporary extra height.
    anchor_name = "m-entry-070"
    anchor = pathfm.entry(anchor_name, "rename-target").find(role="panel")
    pathfm.settle(anchor)
    before = anchor.screen_bounds()
    wait_for_visible_commit(pathfm, original)

    pathfm.keyboard.press("F2")
    field = pathfm.editable_field()
    pathfm.wait(lambda: field.text == original, "the visible row's rename editor")
    pathfm.settle(field)
    assert anchor.screen_bounds() == before
    pathfm.keyboard.type_text(final_name)
    pathfm.wait(lambda: field.text == final_name, "the replacement name")
    pathfm.keyboard.press("Return")
    destination = pathfm.fixture.path("rename-target/" + final_name)
    pathfm.wait(destination.exists, "the visible row renamed on disk")
    pathfm.wait_for_entry_gone(original, "rename-target")
    assert not pathfm.fixture.path("rename-target/" + original).exists()
    assert destination.read_text() == "body\n"
    wait_for_visible_commit(pathfm, final_name)
    anchor = pathfm.entry(anchor_name, "rename-target").find(role="panel")
    pathfm.settle(anchor)
    assert anchor.screen_bounds() == before


@pytest.mark.parametrize("mode", ("Columns", "List"))
@pytest.mark.usefixtures("unreserved_columns")
def test_click_away_rename_respects_navigation(pathfm, mode):
    field, original = begin_long_directory_rename(pathfm, "file", False, mode)
    pathfm.keyboard.type_text("a-final")
    pathfm.wait(lambda: field.text == "a-final", "the final name in the editor")
    if mode == "Columns":
        # The root column remains visible while the long child column is scrolled.
        pathfm.pointer.click(pathfm.entry("documents", pathfm.fixture.root.name))
    else:
        pathfm.pointer.click(pathfm.sidebar_button("Home"))
    destination = pathfm.fixture.path("rename-target/a-final")
    pathfm.wait(destination.exists, "the rename on disk")
    if mode == "Columns":
        pathfm.wait_for_directory("documents")
        pathfm.wait_for_selection(["documents"], pathfm.fixture.root.name)
    else:
        pathfm.wait_for_directory("home")
    assert not pathfm.fixture.path("rename-target/" + original).exists()
    assert "rename-target" not in pathfm.pane_names()


@pytest.mark.parametrize("mode", ("Columns", "List"))
def test_already_visible_created_item_preserves_scroll(pathfm, mode):
    pathfm.switch_view(mode)
    pathfm.fixture.path("rename-target").mkdir()
    for name in ["a-anchor"] + [f"z-entry-{index:03d}" for index in range(80)]:
        pathfm.fixture.path("rename-target/" + name).write_text("body\n")
    pathfm.keyboard.press("F5")
    pathfm.entry("rename-target")
    pathfm.open_directory("rename-target")
    pathfm.keyboard.press("Home")
    pathfm.wait_for_selection(["a-anchor"], "rename-target")
    anchor = pathfm.entry("a-anchor", "rename-target").find(role="panel")
    pathfm.settle(anchor)
    before = anchor.screen_bounds()
    bounds = pathfm.entry_container("rename-target").screen_bounds()
    pathfm.pointer.right_click(pathfm.pane("rename-target"),
                               at=(bounds.x + 1, bounds.y + bounds.height // 2))
    pathfm.choose_menu_item("New File")
    field = pathfm.editable_field()
    original = "new file"
    pathfm.wait(lambda: field.text == original, "the created item's editor")
    pathfm.settle(field)
    assert pathfm.entry("a-anchor", "rename-target").find(role="panel").screen_bounds() == before
    pathfm.keyboard.type_text(original + " renamed")
    pathfm.keyboard.press("Return")
    pathfm.wait(pathfm.fixture.path("rename-target/" + original + " renamed").exists,
                "the created item renamed on disk")
    wait_for_visible_commit(pathfm, original + " renamed")
    anchor = pathfm.entry("a-anchor", "rename-target").find(role="panel")
    pathfm.settle(anchor)
    assert anchor.screen_bounds() == before
