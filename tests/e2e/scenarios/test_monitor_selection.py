# SPDX-License-Identifier: MIT

import pytest

from harness.fixtures import FixtureTree
from harness.modes import ALL_MODES, NEXT_ENTRY_KEY


@pytest.fixture
def fixture_tree():
    fixture = FixtureTree.create(
        {f"{index:03}.txt": f"{index}\n" for index in range(100)}
    )
    try:
        yield fixture
    finally:
        fixture.cleanup()


def visible_entries(pathfm):
    viewport = next(
        node.screen_bounds()
        for node in pathfm.entry_container().ancestors()
        if node.role == "scroll pane"
    )
    return [
        node for node in pathfm.entries()
        if viewport.y <= node.screen_bounds().y < viewport.y + viewport.height
    ]


@pytest.mark.parametrize("mode", ALL_MODES)
def test_background_rename_preserves_scroll_and_multiselection(pathfm, mode):
    pathfm.select_entry("001.txt")
    pathfm.pointer.click(pathfm.entry("003.txt"), modifiers=["ctrl"])
    pathfm.wait_for_selection(["001.txt", "003.txt"])
    before = visible_entries(pathfm)[0].name
    pathfm.pointer.scroll(at=pathfm.pane().screen_bounds().center, clicks=2)
    pathfm.wait(
        lambda: visible_entries(pathfm) and visible_entries(pathfm)[0].name != before,
        "the listing to scroll",
    )
    visible = visible_entries(pathfm)
    marker = pathfm.settle(visible[len(visible) // 2])
    scrolled = marker.screen_bounds().y

    source_name = visible[-1].name
    source = pathfm.fixture.path(source_name)
    destination_name = source.stem + "-renamed.txt"
    source.write_text("updated before rename\n")
    source.rename(pathfm.fixture.path(destination_name))
    pathfm.entry(destination_name)
    pathfm.wait_for_entry_gone(source_name)
    pathfm.settle(marker)

    assert marker.screen_bounds().y == scrolled
    pathfm.pointer.scroll(at=pathfm.pane().screen_bounds().center, clicks=20, down=False)
    pathfm.wait_for_selection(["001.txt", "003.txt"])
    assert not source.exists()
    assert pathfm.fixture.path(destination_name).read_text() == "updated before rename\n"


@pytest.mark.parametrize("mode", ALL_MODES)
def test_keyboard_navigation_survives_background_insertion(pathfm, mode):
    pathfm.select_entry("003.txt")
    pathfm.wait_for_focused_entry("003.txt")
    pathfm.fixture.path("000-new.txt").write_text("new entry\n")
    pathfm.entry("000-new.txt")
    pathfm.keyboard.press(NEXT_ENTRY_KEY[mode])
    pathfm.wait_for_focused_entry("004.txt")
    pathfm.wait_for_selection(["004.txt"])
