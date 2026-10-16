# SPDX-License-Identifier: MIT
import pytest
from PIL import Image

from harness.fixtures import FixtureTree
from harness.modes import ALL_MODES


@pytest.fixture
def fixture_tree():
    tree = FixtureTree.create({
        "a.txt": "root preview\n",
        "z.rar": "unsupported fixture\n",
        "Alpha": {"a.txt": "alpha preview\n", "Beta": {"Gamma": {"Delta": {"a.txt": "delta preview\n"}}}},
    })
    Image.new("RGB", (80, 40), "green").save(tree.path("image.png"))
    try:
        yield tree
    finally:
        tree.cleanup()


def preview_option(pathfm):
    pathfm.open_appearance_menu()
    return pathfm.wait(
        lambda: pathfm.window.find(role="toggle button", name="Preview panel"),
        "the session preview toggle",
    )


@pytest.mark.parametrize("mode", ALL_MODES)
def test_preview_mode_survives_unsupported_selections_and_matches_appearance(pathfm, mode):
    pathfm.switch_view(mode)
    pathfm.select_entry("z.rar")
    option = preview_option(pathfm)
    if mode == "Columns":
        assert option.has_state("pressed"), "Columns reserves previews from startup"
        pathfm.pointer.click(option)
        pathfm.wait_for_menu_closed()
        option = preview_option(pathfm)
    assert option.find(role="label", name="Space") is not None
    assert not option.has_state("pressed")
    pathfm.pointer.click(option)
    pathfm.wait_for_menu_closed()
    if mode in ["Columns", "Icons"]:
        pathfm.wait(lambda: pathfm.preview_shows("No preview for this selection"), "the reserved preview space")
    else:
        assert pathfm.preview() is None
    option = preview_option(pathfm)
    assert option.has_state("pressed"), option.states
    pathfm.dismiss_menu()
    pathfm.select_entry("a.txt")
    pathfm.wait(lambda: pathfm.preview_shows("root preview"), "automatic preview after unsupported selection")
    pathfm.select_entry_with_keyboard("z.rar")
    if mode in ["Columns", "Icons"]:
        pathfm.wait(lambda: pathfm.preview_shows("No preview for this selection"), "the empty preview slot")
        assert not pathfm.preview_shows("root preview")
        assert not pathfm.preview().find(role="button", name="Open in default application").has_state("sensitive")
        pathfm.pointer.click(pathfm.pane(), at=pathfm.background_point())
        pathfm.wait_for_selection([])
        pathfm.wait(lambda: pathfm.preview_shows("No preview for this selection"), "the cleared selection's preview slot")
    else:
        pathfm.wait(lambda: pathfm.preview() is None, "unsupported selection to hide the panel")
    option = preview_option(pathfm)
    assert option.has_state("pressed"), option.states
    pathfm.pointer.click(option)
    pathfm.wait_for_menu_closed()
    pathfm.wait(lambda: pathfm.preview() is None, "the disabled preview panel to close")
    pathfm.select_entry("a.txt")
    assert pathfm.preview() is None
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview_shows("root preview"), "Space to enable the panel")
    option = preview_option(pathfm)
    assert option.has_state("pressed"), option.states
    pathfm.dismiss_menu()
    pathfm.open_directory("Alpha")
    pathfm.select_entry_with_keyboard("a.txt")
    pathfm.wait(lambda: pathfm.preview_shows("alpha preview"), "preview after directory navigation")
    pathfm.select_entry_with_keyboard("Beta")
    pathfm.keyboard.press("space")
    pathfm.wait_for_directory("Beta")
    option = preview_option(pathfm)
    assert option.has_state("pressed")
    pathfm.dismiss_menu()
    if mode == "Columns":
        # Focus stays on the Appearance button, so the deepest pane is the
        # column mirrored from Beta's cursor rather than Beta itself.
        assert pathfm.selected_names("Alpha") == ["Beta"]
    else:
        assert pathfm.current_directory() == "Beta"


@pytest.mark.preferences(browser_mode="icons", single_click_previews=False)
def test_icons_keep_their_layout_until_preview_mode_is_explicitly_toggled(pathfm):
    pathfm.select_entry("a.txt")
    full_width = pathfm.pane().screen_bounds().width
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview_shows("root preview"), "the initial preview")
    width = pathfm.pane().screen_bounds().width
    assert width < full_width

    def positions():
        return {name: pathfm.entry(name).screen_bounds() for name in ["Alpha", "a.txt", "image.png", "z.rar"]}

    layout = positions()

    def assert_layout():
        for name, actual in positions().items():
            expected = layout[name]
            assert abs(actual.x - expected.x) <= 1 and abs(actual.y - expected.y) <= 1, (name, expected, actual)
            assert actual.width == expected.width and actual.height == expected.height

    for name, expected in [("z.rar", "No preview for this selection"), ("image.png", "image/png"), ("Alpha", "No preview for this selection"), ("a.txt", "root preview")]:
        pathfm.select_entry_with_keyboard(name)
        pathfm.wait(lambda: pathfm.preview_shows(expected), f"the preview for {name}")
        assert pathfm.pane().screen_bounds().width == width
        assert_layout()
        if name in ["z.rar", "Alpha"]:
            assert not pathfm.preview_shows("root preview")
            assert pathfm.preview().find(role="label", name="a.txt") is None
            assert not pathfm.preview().find(role="button", name="Open in default application").has_state("sensitive")

    pathfm.pointer.click(pathfm.pane(), at=pathfm.background_point())
    pathfm.wait_for_selection([])
    pathfm.wait(lambda: pathfm.preview_shows("No preview for this selection"), "empty selection without reflow")
    assert_layout()
    pathfm.open_directory("Alpha")
    pathfm.wait(lambda: pathfm.preview_shows("No preview for this selection"), "the folder's preview slot")
    assert pathfm.pane().screen_bounds().width == width
    pathfm.select_entry("a.txt")
    pathfm.wait(lambda: pathfm.preview_shows("alpha preview"), "a preview inside the folder")
    assert pathfm.pane().screen_bounds().width == width
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview() is None and pathfm.pane().screen_bounds().width == full_width, "intentional toggle to restore the full grid")
    for name in ["Beta", "a.txt"]:
        pathfm.select_entry(name)
        assert pathfm.preview() is None
        assert pathfm.pane().screen_bounds().width == full_width


@pytest.mark.preferences(browser_mode="columns", single_click_previews=False)
def test_peek_click_reveals_a_column_without_activating_rows_or_toolbar_actions(pathfm):
    option = preview_option(pathfm)
    assert option.has_state("pressed")
    pathfm.pointer.click(option)
    pathfm.wait_for_menu_closed()
    browser_left = pathfm.pane().screen_bounds().x
    for name in ["Alpha", "Beta", "Gamma", "Delta"]:
        pathfm.open_directory(name)
    def pane_count():
        return len(pathfm.window.find_all(description="Columns view", rendered=False))

    before = pane_count()
    peek = pathfm.wait(
        lambda: pathfm.window.find(role="button", name="Reveal Alpha column"),
        "a clickable parent-column peek",
    )
    bounds = peek.screen_bounds()
    heading = pathfm.pane("Alpha").find(role="label", name="Alpha", rendered=False)
    assert heading is not None
    pathfm.pointer.double_click(peek, at=(bounds.center[0], heading.screen_bounds().center[1]))
    pathfm.wait(lambda: pathfm.focused_name() == "Beta", "focus in the revealed parent")
    assert pane_count() == before
    pathfm.wait(
        lambda: pathfm.pane("Alpha").screen_bounds().x >= pathfm.sidebar_button("Home").screen_bounds().x,
        "the entire focused parent",
    )
    child = pathfm.wait(
        lambda: pathfm.window.find(role="button", name="Reveal Delta column"),
        "a clickable right-hand column peek",
    )
    pathfm.pointer.click(child)
    pathfm.wait(lambda: pathfm.pane("Delta").screen_bounds().x + pathfm.pane("Delta").screen_bounds().width <= pathfm.window_bounds().width, "the revealed child column")
    assert pane_count() == before
    parent = pathfm.wait(lambda: pathfm.window.find(role="button", name="Reveal Alpha column"), "the parent peek again")
    pathfm.pointer.click(parent)
    pathfm.wait(lambda: pathfm.focused_name() == "Beta", "the parent to receive focus")
    pathfm.select_entry("a.txt", directory="Alpha")
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview_shows("alpha preview"), "the focused parent's preview")

    def focused_column_fits():
        column = pathfm.pane("Alpha").screen_bounds()
        return column.x >= browser_left and column.x + column.width <= pathfm.preview().screen_bounds().x

    pathfm.wait(focused_column_fits, "the focused parent, not the rightmost column, to remain visible")
    assert pane_count() == before
