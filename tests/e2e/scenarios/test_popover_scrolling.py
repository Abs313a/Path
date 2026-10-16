# SPDX-License-Identifier: MIT
"""Outside wheel ticks dismiss browser panels and only scroll the pointed listing."""

import pytest

from harness.fixtures import FixtureTree

PANELS = [
    pytest.param(
        "Columns",
        "sort",
        marks=pytest.mark.preferences(browser_mode="columns"),
        id="sort-columns",
    ),
    pytest.param(
        "List",
        "appearance",
        marks=pytest.mark.preferences(browser_mode="list"),
        id="appearance-list",
    ),
    pytest.param(
        "Icons",
        "thumbnail",
        marks=pytest.mark.preferences(browser_mode="icons"),
        id="thumbnail-icons",
    ),
]


@pytest.fixture
def fixture_tree():
    files = {f"{index:03}.txt": f"{index}\n" for index in range(200)}
    fixture = FixtureTree.create({"nested": files, **files})
    try:
        yield fixture
    finally:
        fixture.cleanup()


def viewport(pathfm, directory=None):
    for node in pathfm.entry_container(directory).ancestors():
        if node.role == "scroll pane":
            return node.screen_bounds()
    raise AssertionError("listing has no scroll viewport")


def open_panel(pathfm, panel):
    if panel == "sort":
        pathfm.pointer.click(pathfm.header_button("Choose sort field"))
        role, label = "check menu item", "Folders first"
    elif panel == "appearance":
        pathfm.open_appearance_menu()
        role, label = "radio menu item", "Compact"
    else:
        toggle = pathfm.window.find(role="toggle button", name="Thumbnail size")
        assert toggle is not None and toggle.activate(), "thumbnail menu must be actionable"
        role, label = "label", "Small"
    return pathfm.wait(
        lambda: pathfm.window.find(role=role, name=label),
        f"the {panel} panel to open",
    )


@pytest.mark.parametrize("mode,panel", PANELS)
@pytest.mark.parametrize("target", ["listing", "sidebar", "inside"])
def test_panel_wheel_routing(pathfm, mode, panel, target):
    row = pathfm.entry("005.txt")
    pathfm.settle(row)
    before = row.screen_bounds()
    bounds = viewport(pathfm)
    option = open_panel(pathfm, panel)
    if target == "listing":
        point = (bounds.center[0], bounds.y + bounds.height * 4 // 5)
    elif target == "sidebar":
        point = pathfm.sidebar_button("Home").screen_bounds().center
    else:
        point = option.screen_bounds().center
    pathfm.pointer.scroll(at=point, clicks=1)
    if target == "inside":
        assert pathfm.window.find(role=option.role, name=option.name) is not None
        assert row.screen_bounds() == before
    else:
        pathfm.wait(
            lambda: pathfm.window.find(role=option.role, name=option.name) is None,
            "outside wheel to close the panel",
        )
        if target == "listing":
            pathfm.wait(
                lambda: row.screen_bounds().y < before.y,
                "the same wheel tick to move the listing",
            )
        else:
            assert row.screen_bounds() == before


@pytest.mark.parametrize("pointed_column", ["parent", "child"])
@pytest.mark.usefixtures("unreserved_columns")
def test_outside_wheel_only_moves_the_column_under_the_pointer(pathfm, pointed_column):
    root = pathfm.fixture.root.name
    pathfm.open_directory("nested")
    parent_row = pathfm.entry("005.txt", directory=root)
    child_row = pathfm.entry("005.txt", directory="nested")
    pathfm.settle(parent_row)
    pathfm.settle(child_row)
    parent_before = parent_row.screen_bounds()
    child_before = child_row.screen_bounds()
    option = open_panel(pathfm, "appearance")
    bounds = viewport(pathfm, root if pointed_column == "parent" else "nested")
    pathfm.pointer.scroll(
        at=(bounds.center[0], bounds.y + bounds.height * 4 // 5), clicks=1
    )
    pathfm.wait(
        lambda: pathfm.window.find(role=option.role, name=option.name) is None,
        "outside wheel to close the panel",
    )
    if pointed_column == "parent":
        pathfm.wait(
            lambda: parent_row.screen_bounds().y < parent_before.y, "parent to scroll"
        )
        assert child_row.screen_bounds() == child_before
    else:
        pathfm.wait(
            lambda: child_row.screen_bounds().y < child_before.y, "child to scroll"
        )
        assert parent_row.screen_bounds() == parent_before
