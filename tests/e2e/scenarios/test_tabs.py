# SPDX-License-Identifier: MIT
"""Live browser tabs, keyboard routing and cross-tab file transfers."""

import pytest
from gi.repository import Atspi

from harness.interaction import MODIFIER_KEYSYMS
from harness.keyboard_layout import QWERTZ
from harness.modes import ALL_MODES


def tab(pathfm, name):
    return pathfm.wait(
        lambda: pathfm.window.find(role="page tab", name=name),
        f"tab {name}",
    )


def selected_tab(pathfm, name):
    return pathfm.wait(
        lambda: tab(pathfm, name).has_state("selected"),
        f"active tab {name}",
    )


@pytest.mark.preferences(browser_mode="columns")
def test_folder_click_keeps_tab_name_until_release_and_keyboard_focus_still_renames(pathfm):
    parent = "documents"
    pathfm.fixture.path("documents/alpha").mkdir()
    pathfm.fixture.path("documents/beta").mkdir()
    pathfm.keyboard.press("ctrl+t")
    pathfm.keyboard.press("ctrl+l")
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text(str(pathfm.fixture.path(parent)))
    pathfm.keyboard.press("Return")
    pathfm.wait_for_directory(parent)
    pathfm.open_directory("alpha")
    selected_tab(pathfm, "alpha")
    # The strip only scrolls when its columns and the reserved preview overflow.
    scrollbar = pathfm.window.find(role="scroll bar", states={"horizontal"})
    if scrollbar is not None:
        value = Atspi.Accessible.get_value_iface(scrollbar.accessible)
        assert Atspi.Value.set_current_value(value, 0.0)
    target = pathfm.settle(pathfm.entry("beta", directory=parent))
    origin = pathfm.pointer.drag_origin(target)
    try:
        pathfm.pointer.drag_points(origin, origin, release=False)
        pathfm.settle(target)
        pathfm.wait_for_selection(["beta"], parent)
        assert pathfm.window.find(role="page tab", name="alpha", states={"selected"}) is not None
        assert pathfm.window.find(role="page tab", name="beta") is None
    finally:
        pathfm.pointer.connection.button(1, False)
    selected_tab(pathfm, "beta")
    pathfm.wait_for_directory("beta")
    pathfm.wait_for_selection([], "beta")
    pathfm.keyboard.press("Left")
    pathfm.wait(
        lambda: pathfm.window.find(role="page tab", name=parent, states={"selected"}),
        "parent tab name after deliberate keyboard focus",
    )
    pathfm.keyboard.press("Right")
    selected_tab(pathfm, "beta")


@pytest.mark.parametrize("tenxer", [
    pytest.param(False, marks=pytest.mark.preferences(tenxer_mode=False)),
    pytest.param(True, marks=pytest.mark.preferences(tenxer_mode=True)),
])
def test_tabs_keep_locations_and_support_numbered_shortcuts(pathfm, keyboard_layout, tenxer):
    root = pathfm.fixture.root.name
    pathfm.select_entry("todo.txt")
    pathfm.keyboard.press("ctrl+t")
    pathfm.open_directory("archive")
    selected_tab(pathfm, "archive")
    ctrl, shift = MODIFIER_KEYSYMS["ctrl"], MODIFIER_KEYSYMS["shift"]
    pathfm.keyboard.connection.key(ctrl, True)
    pathfm.keyboard.connection.key(shift, True)
    try:
        pathfm.wait(
            lambda: pathfm.window.find(role="label", name="1"),
            "tab number hints while Ctrl+Shift is held",
        )
    finally:
        pathfm.keyboard.connection.key(shift, False)
        pathfm.keyboard.connection.key(ctrl, False)
    pathfm.keyboard.press("ctrl+shift+1")
    selected_tab(pathfm, root)
    pathfm.wait_for_selection(["todo.txt"], root)
    pathfm.keyboard.press("ctrl+Tab")
    selected_tab(pathfm, "archive")
    pathfm.keyboard.press("ctrl+shift+Tab")
    selected_tab(pathfm, root)
    # German Shift+2 types ", yet the digit row still numbers the tabs.
    with keyboard_layout(QWERTZ):
        pathfm.keyboard.press("ctrl+shift+2")
        selected_tab(pathfm, "archive")
    pathfm.keyboard.press("ctrl+t")
    pathfm.keyboard.press("alt+Up")
    pathfm.wait_for_directory(root)
    pathfm.open_directory("pictures")
    selected_tab(pathfm, "pictures")
    for shortcut, names in [
        ("ctrl+Page_Up", ["archive", root, "pictures"]),
        ("ctrl+Page_Down", [root, "archive", "pictures"]),
    ]:
        pathfm.keyboard.press("ctrl+l")
        pathfm.wait(
            lambda: pathfm.window.find(role="text", name="Location (Ctrl+L)", states={"focused"}),
            "location editor to take focus",
        )
        for name in names:
            pathfm.keyboard.press(shortcut)
            selected_tab(pathfm, name)
    for shortcut, order in [
        ("ctrl+shift+Page_Up", [root, "pictures", "archive"]),
        ("ctrl+shift+Page_Up", ["pictures", root, "archive"]),
        ("ctrl+shift+Page_Up", ["pictures", root, "archive"]),
        ("ctrl+shift+Page_Down", [root, "pictures", "archive"]),
        ("ctrl+shift+Page_Down", [root, "archive", "pictures"]),
        ("ctrl+shift+Page_Down", [root, "archive", "pictures"]),
    ]:
        pathfm.keyboard.press("ctrl+l")
        field = pathfm.wait(
            lambda: pathfm.window.find(role="text", name="Location (Ctrl+L)", states={"focused"}),
            "location editor to take focus",
        )
        pathfm.keyboard.press(shortcut)
        selected_tab(pathfm, "pictures")
        pathfm.wait(lambda: field.has_state("focused"), "reordering to preserve location editor focus")
        pathfm.keyboard.press("Escape")
        for index, name in enumerate(order, start=1):
            pathfm.keyboard.press(f"ctrl+shift+{index}")
            selected_tab(pathfm, name)
        pathfm.keyboard.press(f"ctrl+shift+{order.index('pictures') + 1}")
        selected_tab(pathfm, "pictures")
    pathfm.keyboard.press("ctrl+w")
    selected_tab(pathfm, "archive")
    pathfm.keyboard.press("ctrl+w")
    pathfm.wait_for_selection(["todo.txt"], root)
    # The same add control works after the strip collapses.
    pathfm.pointer.click(pathfm.wait(lambda: pathfm.window.find(role="button", name="New tab"), "New tab"))
    pathfm.open_directory("documents")
    selected_tab(pathfm, "documents")
    assert pathfm.environment.read_preferences().get("tenxer_mode") == str(tenxer).lower()


@pytest.mark.parametrize("mode", ALL_MODES)
def test_drop_on_another_tab_moves_files_into_its_location(pathfm, mode):
    root = pathfm.fixture.root.name
    pathfm.keyboard.press("ctrl+t")
    pathfm.open_directory("archive")
    selected_tab(pathfm, "archive")
    pathfm.keyboard.press("ctrl+shift+1")
    selected_tab(pathfm, root)
    source = pathfm.select_entry("todo.txt")
    pathfm.pointer.drag(source, tab(pathfm, "archive"))
    pathfm.wait(lambda: pathfm.fixture.path("archive/todo.txt").exists(), "file transferred to the other tab")
    assert not pathfm.fixture.path("todo.txt").exists()
    assert pathfm.fixture.path("archive/todo.txt").read_text() == "todo\n"


def test_hovering_a_tab_during_drag_allows_a_drop_in_its_listing(pathfm):
    pathfm.fixture.path("documents/projects").mkdir()
    root = pathfm.fixture.root.name
    pathfm.keyboard.press("ctrl+t")
    pathfm.wait(
        lambda: pathfm.window.find(role="page tab", name=root, states={"selected"}),
        "the new root tab to become active before pointer navigation",
    )
    pathfm.open_directory("documents")
    selected_tab(pathfm, "documents")
    pathfm.keyboard.press("ctrl+shift+1")
    selected_tab(pathfm, root)
    source = pathfm.select_entry("todo.txt")
    pathfm.pointer.drag_points(
        pathfm.pointer.drag_origin(source),
        tab(pathfm, "documents").screen_bounds().center,
        release=False,
    )
    try:
        selected_tab(pathfm, "documents")
        target = pathfm.entry("projects")
        # A drag icon can match a row's native-surface size. Avoid the legacy
        # popup-origin correction while the drag surface is alive.
        x, y = target.window_bounds().center
        origin = pathfm.window.screen_bounds()
        pathfm.pointer.move_to(origin.x + x, origin.y + y)
    finally:
        pathfm.pointer.connection.button(1, False)
    pathfm.wait(lambda: pathfm.fixture.path("documents/projects/todo.txt").exists(), "file dropped after switching tabs during drag")
    assert not pathfm.fixture.path("todo.txt").exists()


def test_dragging_tab_labels_changes_numbered_order(pathfm):
    root = pathfm.fixture.root.name
    pathfm.keyboard.press("ctrl+t")
    pathfm.open_directory("archive")
    selected_tab(pathfm, "archive")
    pathfm.pointer.drag(tab(pathfm, "archive"), tab(pathfm, root))
    pathfm.keyboard.press("ctrl+shift+2")
    selected_tab(pathfm, root)
    pathfm.keyboard.press("ctrl+shift+1")
    selected_tab(pathfm, "archive")
    pathfm.keyboard.press("ctrl+Page_Down")
    selected_tab(pathfm, root)
    pathfm.keyboard.press("ctrl+Page_Up")
    selected_tab(pathfm, "archive")


def tab_chord(pathfm, suffix):
    pathfm.keyboard.press("t")
    pathfm.keyboard.press(suffix)


@pytest.mark.preferences(tenxer_mode=True)
@pytest.mark.parametrize("mode", ALL_MODES)
def test_tenxer_tab_chords_create_select_close_and_respect_text_input(pathfm, mode):
    root = pathfm.fixture.root.name
    pathfm.select_entry("todo.txt")
    pathfm.keyboard.press("ctrl+l")
    field = pathfm.wait(lambda: pathfm.window.find(role="text", name="Location (Ctrl+L)"), "location editor")
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text("tntt")
    pathfm.wait(lambda: field.text == "tntt", "tab chord letters to remain literal text")
    pathfm.keyboard.press("Escape")
    pathfm.keyboard.press("t")
    pathfm.wait(lambda: pathfm.window.find(role="label", name="t-"), "tab chord options")
    pathfm.keyboard.press("Escape")
    pathfm.keyboard.press("n")
    pathfm.wait_for_selection(["todo.txt"], root)
    tab_chord(pathfm, "n")
    pathfm.open_directory("archive")
    selected_tab(pathfm, "archive")
    tab_chord(pathfm, "1")
    selected_tab(pathfm, root)
    pathfm.wait_for_selection(["todo.txt"], root)
    tab_chord(pathfm, "2")
    selected_tab(pathfm, "archive")
    tab_chord(pathfm, "n")
    pathfm.keyboard.press("alt+Up")
    pathfm.wait_for_directory(root)
    pathfm.open_directory("pictures")
    selected_tab(pathfm, "pictures")
    tab_chord(pathfm, "t")
    selected_tab(pathfm, "archive")
    tab_chord(pathfm, "t")
    selected_tab(pathfm, root)
    pathfm.wait_for_selection(["todo.txt"], root)
    tab_chord(pathfm, "t")
    selected_tab(pathfm, "pictures")
    tab_chord(pathfm, "x")
    selected_tab(pathfm, "archive")
    tab_chord(pathfm, "x")
    tab_chord(pathfm, "t")
    pathfm.wait_for_selection(["todo.txt"], root)


@pytest.mark.preferences(tenxer_mode=True)
def test_zero_selects_the_tenth_tab_with_chords_and_numbered_shortcuts(pathfm):
    pathfm.entry("todo.txt")
    for number in range(2, 11):
        pathfm.fixture.path(f"tab-{number}").mkdir()
    pathfm.keyboard.press("F5")
    pathfm.entry("tab-10")
    root = pathfm.fixture.root.name
    for number in range(2, 11):
        pathfm.keyboard.press("ctrl+shift+1")
        tab_chord(pathfm, "n")
        pathfm.open_directory(f"tab-{number}")
        selected_tab(pathfm, f"tab-{number}")
    tab_chord(pathfm, "1")
    selected_tab(pathfm, root)
    tab_chord(pathfm, "0")
    selected_tab(pathfm, "tab-10")
    pathfm.keyboard.press("ctrl+shift+1")
    selected_tab(pathfm, root)
    pathfm.keyboard.press("ctrl+shift+0")
    selected_tab(pathfm, "tab-10")
    tab_chord(pathfm, "x")
    selected_tab(pathfm, "tab-9")
    tab_chord(pathfm, "0")
    selected_tab(pathfm, "tab-9")


def test_ctrl_drop_on_a_tab_copies_without_removing_the_source(pathfm):
    root = pathfm.fixture.root.name
    pathfm.keyboard.press("ctrl+t")
    pathfm.open_directory("archive")
    selected_tab(pathfm, "archive")
    pathfm.keyboard.press("ctrl+shift+1")
    selected_tab(pathfm, root)
    source = pathfm.select_entry("todo.txt")
    pathfm.pointer.drag_points(
        pathfm.pointer.drag_origin(source),
        tab(pathfm, "archive").screen_bounds().center,
        modifiers=["ctrl"],
    )
    pathfm.wait(lambda: pathfm.fixture.path("archive/todo.txt").exists(), "file copied across tabs")
    assert pathfm.fixture.path("todo.txt").read_bytes() == pathfm.fixture.path("archive/todo.txt").read_bytes()
