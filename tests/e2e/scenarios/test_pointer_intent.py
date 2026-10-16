# SPDX-License-Identifier: MIT
"""Content drags, inert-space marquees, and release-only previews in every mode."""

import time

import pytest

from harness.artifacts import ArtifactCollector
from harness.interaction import SEPARATE_CLICK_GAP
from harness.modes import ALL_MODES


@pytest.mark.preferences(single_click_previews=True)
@pytest.mark.parametrize("mode", ALL_MODES)
@pytest.mark.parametrize("origin", ["icon", "name"])
def test_file_drag_does_not_open_preview(pathfm, mode, origin):
    source = pathfm.entry("todo.txt")
    if origin == "icon":
        start = pathfm.pointer.drag_origin(source)
    else:
        label = source.find(role="label", name="todo.txt")
        assert label is not None
        bounds = label.screen_bounds()
        start = bounds.center if mode == "Icons" else (bounds.x + 4, bounds.center[1])
    target = pathfm.entry("archive")

    def assert_no_preview_on_press():
        pathfm.entry("todo.txt")
        assert pathfm.preview() is None, "a held press must not open a preview"

    pathfm.pointer.drag_points(
        start, target.screen_bounds().center, release=False,
        after_press=assert_no_preview_on_press,
    )
    try:
        assert pathfm.preview() is None, "crossing the drag threshold must suppress preview"
    finally:
        pathfm.pointer.connection.button(1, False)
    pathfm.wait(lambda: pathfm.fixture.path("archive/todo.txt").exists(), "the file drop")
    assert not pathfm.fixture.path("todo.txt").exists()
    assert pathfm.preview() is None


@pytest.mark.preferences(single_click_previews=True)
@pytest.mark.parametrize("mode", ALL_MODES)
@pytest.mark.parametrize(
    "origin,initial",
    [("content", "none"), ("inert", "none"), ("content", "group")],
    ids=["content", "inert", "content-group"],
)
def test_simple_click_still_opens_preview(pathfm, mode, origin, initial):
    root = pathfm.fixture.root.name
    if initial == "group":
        pathfm.wait_for_selection(["archive"], root)
        pathfm.click_entry_with("todo.txt", ["ctrl"], root)
        pathfm.wait_for_selection(["archive", "todo.txt"], root)
        time.sleep(SEPARATE_CLICK_GAP)
    at = _inert_point(pathfm, "todo.txt", mode) if origin == "inert" else None
    pathfm.pointer.click(pathfm.entry("todo.txt", root), at=at)
    pathfm.wait(lambda: pathfm.preview_shows("todo"), "preview after a simple click")
    if initial == "group":
        pathfm.wait_for_selection(["todo.txt"], root)


def _full_directory(pathfm):
    folder = pathfm.fixture.path("full")
    folder.mkdir()
    for index in range(180):
        (folder / f"{index:03}.txt").write_text(f"{index}\n")
    pathfm.open_directory("full")
    return folder


def _scroll_back_to(pathfm, name):
    def on_screen():
        entry = next((entry for entry in pathfm.entries() if entry.name == name), None)
        if entry is not None and pathfm.on_screen(entry):
            return entry
        pathfm.pointer.scroll(pathfm.pane().screen_bounds().center, clicks=10, down=False)
        return None

    pathfm.settle(pathfm.wait(on_screen, f"{name} to scroll back into view"))


def _inert_point(pathfm, name, mode):
    row = pathfm.entry(name)
    if mode == "Icons":
        icon = row.find(role="image")
        assert icon is not None
        bounds = icon.screen_bounds()
        return bounds.x - 6, bounds.center[1]
    label = row.find(role="label", name=name)
    assert label is not None
    bounds = label.screen_bounds()
    return bounds.x + bounds.width * 2 // 3, bounds.center[1]


@pytest.mark.preferences(single_click_previews=True)
@pytest.mark.parametrize("mode", ALL_MODES)
@pytest.mark.parametrize(
    "modifiers,select_all",
    [
        pytest.param((), False, id="plain"),
        pytest.param(("ctrl",), False, id="ctrl"),
        # Every row is selected, so Alt starts the marquee over one.
        pytest.param(("ctrl", "alt"), True, id="ctrl-over-select-all"),
    ],
)
def test_marquee_begins_beside_content_in_a_full_pane(pathfm, mode, modifiers, select_all):
    folder = _full_directory(pathfm)
    before = sorted(folder.iterdir())
    if select_all:
        pathfm.keyboard.press("ctrl+a")
        pathfm.wait(
            lambda: pathfm.window.find(role="label", name=f"{len(before)} files selected"),
            "select all before the marquee",
        )
        _scroll_back_to(pathfm, "000.txt")
    initial = set(pathfm.selected_names())
    start = _inert_point(pathfm, "001.txt", mode)
    end = _inert_point(pathfm, "011.txt", mode)
    pathfm.pointer.drag_points(
        start, (end[0] + 3, end[1]), modifiers=modifiers
    )

    def expected(name):
        return name not in initial if "ctrl" in modifiers else True

    pathfm.wait(
        lambda: len(pathfm.selected_names()) > 1
        and all(
            (name in pathfm.selected_names()) == expected(name)
            for name in ("001.txt", "011.txt")
        ),
        "marquee selection beside occupied rows",
    )
    if select_all:
        # The description holds the count in every footer wording; cleared rows lie
        # between the band's ends.
        def footer_counts_the_remaining_fill():
            entries = pathfm.entries()
            ends = [entry for entry in entries if entry.name in ("001.txt", "011.txt")]
            if len(ends) != 2 or any(
                entry.has_state("selected") or not pathfm.on_screen(entry) for entry in ends
            ):
                return None
            cleared = sum(not entry.has_state("selected") for entry in entries)
            remaining = f"{len(before) - cleared} of {len(before)} items selected"
            return pathfm.window.find(
                role="label",
                predicate=lambda node: node.description.startswith(remaining),
            )

        pathfm.wait(
            footer_counts_the_remaining_fill,
            "the footer to count the fill left by the marquee",
        )
    assert pathfm.preview() is None
    assert sorted(folder.iterdir()) == before


@pytest.mark.preferences(browser_mode="icons")
@pytest.mark.parametrize("text_size", [
    pytest.param(13, marks=pytest.mark.preferences(text_size=13)),
    pytest.param(28, marks=pytest.mark.preferences(text_size=28)),
])
@pytest.mark.parametrize("corner", ["leading", "trailing"])
def test_pane_corner_marquee_does_not_resize_sidebar(pathfm, text_size, corner):
    folder = _full_directory(pathfm)
    before = sorted(folder.iterdir())
    sidebar = pathfm.sidebar_button("Home").parent
    while sidebar is not None and sidebar.role != "scroll pane":
        sidebar = sidebar.parent
    assert sidebar is not None
    sidebar_before = sidebar.screen_bounds()
    pane = pathfm.pane().screen_bounds()
    container = pathfm.entry_container().screen_bounds()
    x = pane.x + 2 if corner == "leading" else container.x + container.width - 2
    start = (x, container.y + 2)
    end = pathfm.entry("003.txt").screen_bounds().center
    pathfm.pointer.drag_points(start, end)
    pathfm.settle(pathfm.pane())
    assert sidebar.screen_bounds().width == sidebar_before.width, (
        f"{text_size}px {corner} pane corner must select files, not resize the sidebar"
    )
    pathfm.wait(
        lambda: "003.txt" in pathfm.selected_names() and len(pathfm.selected_names()) > 1,
        "a marquee from the pane corner to select files",
    )
    selected = pathfm.selected_names()
    divider = ((sidebar_before.x + sidebar_before.width + pane.x) // 2, container.center[1])
    pathfm.pointer.drag_points(divider, (divider[0] + 40, divider[1]))
    pathfm.wait(
        lambda: sidebar.screen_bounds().width >= sidebar_before.width + 30,
        "dragging the actual sidebar divider to resize it",
    )
    assert pathfm.selected_names() == selected
    assert sorted(folder.iterdir()) == before


@pytest.mark.parametrize("mode", ALL_MODES)
def test_modifier_clicks_on_inert_space_still_select(pathfm, mode):
    _full_directory(pathfm)
    pathfm.select_entry("000.txt")
    pathfm.pointer.click(
        pathfm.entry("002.txt"),
        at=_inert_point(pathfm, "002.txt", mode),
        modifiers=("ctrl",),
    )
    pathfm.wait_for_selection(["000.txt", "002.txt"])
    pathfm.pointer.click(
        pathfm.entry("004.txt"),
        at=_inert_point(pathfm, "004.txt", mode),
        modifiers=("shift",),
    )
    pathfm.wait_for_selection(["002.txt", "003.txt", "004.txt"])


@pytest.mark.parametrize("mode", ALL_MODES)
@pytest.mark.parametrize(
    "selected,open_after_drop",
    [
        pytest.param(
            False,
            False,
            marks=pytest.mark.preferences(open_folder_after_drop=False),
            id="unselected-stay",
        ),
        pytest.param(
            False,
            True,
            marks=pytest.mark.preferences(open_folder_after_drop=True),
            id="unselected-open",
        ),
        pytest.param(
            True,
            False,
            marks=pytest.mark.preferences(open_folder_after_drop=False),
            id="selected-stay",
        ),
    ],
)
def test_ctrl_drag_from_content_copies_and_keeps_selection(
    pathfm, mode, selected, open_after_drop,
):
    if selected:
        pathfm.select_entry("todo.txt")
    initial_selection = pathfm.selected_names()
    start = pathfm.pointer.drag_origin(pathfm.entry("todo.txt"))
    target = pathfm.entry("archive")
    pathfm.pointer.drag_points(
        start, target.screen_bounds().center, modifiers=("ctrl",)
    )
    pathfm.wait(
        lambda: pathfm.fixture.path("archive/todo.txt").exists(),
        "the ctrl-drag from content to copy the file",
    )
    assert pathfm.fixture.path("todo.txt").exists()
    if open_after_drop:
        pathfm.entry("todo.txt", directory="archive")
        pathfm.wait_for_selection(["todo.txt"])
    else:
        # Pre-selecting the source does not keep the listing selection after drop.
        if not selected:
            pathfm.wait_for_selection(sorted(set(initial_selection) | {"todo.txt"}))
        pathfm.entry("todo.txt", directory=pathfm.fixture.root.name)
        assert "archive" not in pathfm.pane_names()


@pytest.mark.parametrize("mode", ALL_MODES)
def test_shift_drag_from_content_moves_the_file(pathfm, mode):
    start = pathfm.pointer.drag_origin(pathfm.entry("todo.txt"))
    target = pathfm.entry("archive")
    pathfm.pointer.drag_points(
        start, target.screen_bounds().center, modifiers=("shift",)
    )
    pathfm.wait(
        lambda: pathfm.fixture.path("archive/todo.txt").exists(),
        "the shift-drag from content to move the file",
    )
    assert not pathfm.fixture.path("todo.txt").exists()


@pytest.mark.parametrize("mode", ALL_MODES)
def test_sidebar_marquee_still_reaches_the_leading_pane(pathfm, mode):
    root = pathfm.fixture.root.name
    if mode == "Columns":
        pathfm.open_directory("documents")
    home = pathfm.sidebar_button("Home")
    for _ in range(2):
        pathfm.keyboard.press("Home")
        pathfm.keyboard.press("Left")
        if home.has_state("focused"):
            break
    pathfm.wait(lambda: home.has_state("focused"), "keyboard focus in the sidebar")
    sidebar = home.parent
    assert sidebar is not None
    bounds = sidebar.screen_bounds()
    start = (bounds.center[0], bounds.y + bounds.height - 10)
    first = pathfm.entry("readme.md", root).screen_bounds().center
    last = pathfm.entry("todo.txt", root).screen_bounds().center
    pathfm.pointer.drag_points(start, (last[0], first[1]), release=False)
    try:
        pathfm.wait(
            lambda: {"readme.md", "todo.txt"} <= set(pathfm.selected_names(root)),
            "the sidebar marquee to select in the leading pane",
        )
        collection = pathfm.entry_container(root)
        pathfm.wait(
            lambda: any(node.has_state("focused") for _, node in collection.walk()),
            "the marquee target to own focus and active selection feedback during the drag",
        )
        pathfm.screenshot(
            ArtifactCollector(test_name=f"sidebar-marquee-{mode}").directory
            / "selection.png"
        )
    finally:
        pathfm.pointer.connection.button(1, False)
    assert not home.has_state("focused")
    selected = set(pathfm.selected_names(root))
    pathfm.keyboard.press("ctrl+c")
    destination = "selection-copy"
    pathfm.fixture.path(destination).mkdir()
    pathfm.open_directory(destination, root)
    pathfm.paste_into(destination)
    pathfm.wait(
        lambda: set(pathfm.fixture.names(destination)) == selected
        and all(
            pathfm.fixture.path(f"{destination}/{name}").stat().st_size
            == pathfm.fixture.path(name).stat().st_size
            for name in ("readme.md", "todo.txt")
        ),
        "keyboard copy to finish in the marquee target rather than the sidebar or another pane",
    )
    for name in ("readme.md", "todo.txt"):
        assert pathfm.fixture.path(f"{destination}/{name}").read_bytes() == pathfm.fixture.path(
            name
        ).read_bytes()
